
#!/usr/bin/env python3
"""
SISTEMA DE EMERGENCIA WRO - Reto de Obstáculos (LiDAR + Servo + Cámara)
Objetivo: Completar 3 vueltas (12 esquinas) esquivando obstáculos en el trayecto.

Protocolo WRO:
1. Encendido: Inicializa sensores y queda en modo STANDBY.
2. Pulsador de retención: Al cambiar el estado del switch físico (GPIO 17), arranca la carrera.
3. Carrera:
   - Avanza en recta. LiDAR apunta al frente (90°).
   - Si detecta obstáculo frontal cercano (<= DIST_OBSTACULO_CM):
       Detecta color del pilar con cámara CSI (rojo, verde, morado).
       Hace mini barrido: mide a izquierda (0°) y derecha (180°) - rango máximo del servo.
       Esquiva por el lado según regla de colores:
         * Rojo/Morado: esquivar por izquierda
         * Verde: esquivar por derecha
       Si no detecta color, esquiva por el lado con mayor espacio libre.
   - Si detecta pared de contención (<= DIST_PARED_ESQUINA_CM):
       Gira a la derecha y cuenta la esquina.
4. Finalización: Completa 12 esquinas (3 vueltas), frena y se detiene.

NOTA: Con cámara se detecta color del pilar para cumplimiento de regla WRO.
      Sin cámara, el algoritmo esquiva por el lado con más espacio (fallback).

CONFIGURACIÓN: Todos los parámetros se cargan desde config.yaml en el mismo directorio.
"""

import time
import glob
import struct
import serial
import logging
import yaml
import os
import threading
from collections import deque
from dataclasses import dataclass
from typing import Optional

try:
    import cv2
    import numpy as np
    OPENCV_AVAILABLE = True
except ImportError:
    OPENCV_AVAILABLE = False
    cv2 = None
    np = None

try:
    from gpiozero import Button, AngularServo
except ImportError:
    Button = None
    AngularServo = None

# CONFIGURACIÓN DIRECTA

# Cargar configuración desde config.yaml
def cargar_config():
    config_path = os.path.join(os.path.dirname(__file__), "config.yaml")
    try:
        with open(config_path, 'r') as f:
            config = yaml.safe_load(f)
            if config is None:
                config = {}
            return config
    except FileNotFoundError:
        logging.warning(f"Archivo config.yaml no encontrado en {config_path}. Usando valores por defecto.")
        return {}
    except yaml.YAMLError as e:
        logging.error(f"Error al parsear config.yaml: {e}. Usando valores por defecto.")
        return {}

config = cargar_config()

# Conexiones seriales
PUERTO_LIDAR = config.get('serial', {}).get('puerto_lidar', "/dev/serial0")
BAUD_LIDAR = config.get('serial', {}).get('baud_lidar', 115200)
BAUD_ARDUINO = config.get('serial', {}).get('baud_arduino', 115200)

# Servo del LiDAR (para mini barrido de esquiva)
PIN_SERVO_LIDAR = config.get('hardware', {}).get('pin_servo_lidar', 18)
ANGULO_FRENTE = config.get('servo_lidar', {}).get('angulo_frente', 90)      # LiDAR mirando al frente
ANGULO_IZQUIERDA = config.get('servo_lidar', {}).get('angulo_izquierda', 0)   # LiDAR mirando a la izquierda (máximo rango)
ANGULO_DERECHA = config.get('servo_lidar', {}).get('angulo_derecha', 180)    # LiDAR mirando a la derecha (máximo rango)

# Botón de inicio físico (Regla WRO 9.11)
PIN_BOTON_INICIO = config.get('hardware', {}).get('pin_boton_inicio', 17)

# Parámetros de navegación
VUELTAS_OBJETIVO = config.get('navegacion', {}).get('vueltas_objetivo', 3)
ESQUINAS_POR_VUELTA = config.get('navegacion', {}).get('esquinas_por_vuelta', 4)
TOTAL_ESQUINAS = VUELTAS_OBJETIVO * ESQUINAS_POR_VUELTA  # 12 esquinas

# Velocidades (-100 a 100)
VELOCIDAD_CRUCERO = config.get('velocidades', {}).get('crucero', 60)    # Velocidad en tramos rectos
VELOCIDAD_ESQUIVA = config.get('velocidades', {}).get('esquiva', 40)    # Velocidad durante la maniobra de esquiva
VELOCIDAD_GIRO = config.get('velocidades', {}).get('giro', 40)       # Velocidad durante el giro de esquina

# Ángulos del servo de dirección del carro (valores Arduino)
ANGULO_DIRECCION_RECTO = config.get('angulos_direccion', {}).get('recto', 90)
ANGULO_GIRO_DERECHA = config.get('angulos_direccion', {}).get('giro_derecha', 50)    # Giro máximo derecha
ANGULO_GIRO_IZQUIERDA = config.get('angulos_direccion', {}).get('giro_izquierda', 130) # Giro máximo izquierda

# Umbrales de distancia LiDAR (en cm)
DIST_PARED_ESQUINA_CM = config.get('lidar', {}).get('distancia_giro_cm', 75.0)   # Distancia frontal para iniciar giro de esquina
DIST_OBSTACULO_CM = config.get('lidar', {}).get('distancia_obstaculo_cm', 50.0)       # Distancia frontal para detectar pilar obstáculo
DIST_LIBRE_CM = config.get('lidar', {}).get('distancia_despejada_cm', 90.0)           # Distancia a la que se considera la pista despejada

# Tiempos de control de esquina
DURACION_MAX_GIRO_ESQUINA_SEG = config.get('tiempos', {}).get('duracion_max_giro_seg', 1.6)
DURACION_MIN_GIRO_ESQUINA_SEG = config.get('tiempos', {}).get('duracion_min_giro_seg', 0.5)
TIEMPO_COOLDOWN_ESQUINA_SEG = config.get('tiempos', {}).get('cooldown_esquina_seg', 1.4)

# Tiempos de control de esquiva de obstáculo
DURACION_ESQUIVA_SEG = config.get('tiempos', {}).get('duracion_esquiva_seg', 0.8)      # Tiempo máximo con dirección de esquiva aplicada
DURACION_MIN_ESQUIVA_SEG = config.get('tiempos', {}).get('duracion_min_esquiva_seg', 0.3)  # Tiempo mínimo de esquiva forzado

# Tiempo de asentamiento del servo LiDAR para barrido
MS_POR_GRADO_SERVO = config.get('servo_lidar', {}).get('ms_por_grado', 5)         # ~5 ms/grado para barrido rápido

FRECUENCIA_CONTROL_HZ = config.get('navegacion', {}).get('frecuencia_control_hz', 40)     # Tasa del bucle principal

logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s [%(levelname)s] %(message)s'
)
logger = logging.getLogger("EMERGENCIA_OBSTACULOS")

# Configuración de cámara
CAMARA_ENABLED = config.get('camara', {}).get('enabled', False)
CAMARA_WIDTH = config.get('camara', {}).get('width', 640)
CAMARA_HEIGHT = config.get('camara', {}).get('height', 480)
CAMARA_FPS = config.get('camara', {}).get('fps', 30)
CAMARA_BUFFER_SIZE = config.get('camara', {}).get('buffer_size', 2)

# Configuración de detección de colores
COLORES_ENABLED = config.get('colores', {}).get('enabled', False)
REGION_INTERES = config.get('colores', {}).get('region_interes', {'x1': 160, 'y1': 120, 'x2': 480, 'y2': 360})
AREA_MINIMA = config.get('colores', {}).get('area_minima', 500)
CONFIANZA_MINIMA = config.get('colores', {}).get('confianza_minima', 0.3)

# Rangos HSV para colores
COLOR_ROJO = config.get('colores', {}).get('rojo', {'h_min': 0, 'h_max': 10, 's_min': 100, 's_max': 255, 'v_min': 50, 'v_max': 255})
COLOR_VERDE = config.get('colores', {}).get('verde', {'h_min': 40, 'h_max': 80, 's_min': 50, 's_max': 255, 'v_min': 50, 'v_max': 255})
COLOR_MORADO = config.get('colores', {}).get('morado', {'h_min': 130, 'h_max': 160, 's_min': 50, 's_max': 255, 'v_min': 50, 'v_max': 255})


@dataclass
class StampedFrame:
    """Frame con timestamp para sincronización"""
    data: np.ndarray
    timestamp: float
    sequence: int


class CameraStream:
    """Streaming de cámara CSI con thread separado y buffer limitado.
    
    Diseñado según mejores prácticas de percepción robótica:
    - Captura en thread dedicado a la tasa del sensor
    - Procesamiento nunca bloquea la captura
    - Siempre usa el frame más reciente (drop frames antiguos para tiempo real)
    - Timestamp en captura, no en procesamiento
    """
    
    def __init__(self, buffer_size=CAMARA_BUFFER_SIZE, name="camera"):
        self.name = name
        self._buffer = deque(maxlen=buffer_size)
        self._lock = threading.Lock()
        self._new_frame = threading.Event()
        self._running = False
        self._thread = None
        self._sequence = 0
        self._camera = None
        
        # Diagnósticos
        self._capture_times = deque(maxlen=100)
        self._drop_count = 0
        
    def start(self):
        """Iniciar thread de captura"""
        if not OPENCV_AVAILABLE:
            logger.warning("OpenCV no disponible - cámara deshabilitada")
            return False
            
        if not CAMARA_ENABLED:
            logger.info("Cámara deshabilitada en configuración")
            return False
            
        try:
            # Intentar abrir cámara CSI (Raspberry Pi Camera Module)
            self._camera = cv2.VideoCapture(0)
            if not self._camera.isOpened():
                logger.error("No se pudo abrir la cámara")
                return False
                
            self._camera.set(cv2.CAP_PROP_FRAME_WIDTH, CAMARA_WIDTH)
            self._camera.set(cv2.CAP_PROP_FRAME_HEIGHT, CAMARA_HEIGHT)
            self._camera.set(cv2.CAP_PROP_FPS, CAMARA_FPS)
            
            self._running = True
            self._thread = threading.Thread(
                target=self._capture_loop, daemon=True, name=f"{self.name}_capture")
            self._thread.start()
            
            logger.info(f"Cámara CSI iniciada: {CAMARA_WIDTH}x{CAMARA_HEIGHT} @ {CAMARA_FPS} FPS")
            return True
            
        except Exception as e:
            logger.error(f"Error al iniciar cámara: {e}")
            return False
    
    def stop(self):
        """Detener thread de captura"""
        self._running = False
        if self._thread:
            self._thread.join(timeout=2.0)
        if self._camera:
            self._camera.release()
    
    def _capture_loop(self):
        """Loop de captura en thread separado"""
        while self._running:
            t_start = time.monotonic()
            
            try:
                ret, frame = self._camera.read()
                if not ret or frame is None:
                    time.sleep(0.01)
                    continue
                    
                timestamp = time.monotonic()
                
                stamped_frame = StampedFrame(
                    data=frame,
                    timestamp=timestamp,
                    sequence=self._sequence
                )
                self._sequence += 1
                
                with self._lock:
                    if len(self._buffer) == self._buffer.maxlen:
                        self._drop_count += 1
                    self._buffer.append(stamped_frame)
                
                self._new_frame.set()
                self._capture_times.append(time.monotonic() - t_start)
                
            except Exception as e:
                logger.debug(f"[{self.name}] Error de captura: {e}")
                time.sleep(0.01)
    
    def get_latest(self) -> Optional[StampedFrame]:
        """Obtener frame más reciente (no bloqueante). Retorna None si está vacío."""
        with self._lock:
            if self._buffer:
                return self._buffer[-1]
        return None
    
    def get_diagnostics(self) -> dict:
        """Métricas de salud del streaming"""
        if self._capture_times:
            times = list(self._capture_times)
            fps = 1.0 / np.mean(times) if np.mean(times) > 0 else 0
        else:
            fps = 0
        return {
            "sensor": self.name,
            "fps": round(fps, 1),
            "frames_captured": self._sequence,
            "frames_dropped": self._drop_count,
            "buffer_size": len(self._buffer),
            "avg_capture_ms": round(np.mean(times) * 1000, 1) if self._capture_times else 0,
        }


class ColorDetector:
    """Detector de colores (rojo, verde, morado) para pilar WRO.
    
    Usa espacio de color HSV para detección robusta ante variaciones de iluminación.
    """
    
    def __init__(self):
        self.enabled = COLORES_ENABLED and OPENCV_AVAILABLE
        self.roi = REGION_INTERES
        self.area_min = AREA_MINIMA
        self.conf_min = CONFIANZA_MINIMA
        
        # Definir rangos HSV para cada color
        self.rangos = {
            'rojo': (
                np.array([COLOR_ROJO['h_min'], COLOR_ROJO['s_min'], COLOR_ROJO['v_min']]),
                np.array([COLOR_ROJO['h_max'], COLOR_ROJO['s_max'], COLOR_ROJO['v_max']])
            ),
            'verde': (
                np.array([COLOR_VERDE['h_min'], COLOR_VERDE['s_min'], COLOR_VERDE['v_min']]),
                np.array([COLOR_VERDE['h_max'], COLOR_VERDE['s_max'], COLOR_VERDE['v_max']])
            ),
            'morado': (
                np.array([COLOR_MORADO['h_min'], COLOR_MORADO['s_min'], COLOR_MORADO['v_min']]),
                np.array([COLOR_MORADO['h_max'], COLOR_MORADO['s_max'], COLOR_MORADO['v_max']])
            )
        }
        
        # Para el rojo también agregamos el rango alto (170-180)
        self.rangos_rojo_extendido = (
            np.array([170, COLOR_ROJO['s_min'], COLOR_ROJO['v_min']]),
            np.array([180, COLOR_ROJO['s_max'], COLOR_ROJO['v_max']])
        )
        
        if not self.enabled:
            logger.warning("Detector de colores deshabilitado (configuración o OpenCV no disponible)")
        else:
            logger.info("Detector de colores inicializado: rojo, verde, morado")
    
    def detectar(self, frame: np.ndarray) -> Optional[str]:
        """Detectar el color predominante en la región de interés.
        
        Retorna: 'rojo', 'verde', 'morado' o None si no se detecta ningún color
        """
        if not self.enabled or frame is None:
            return None
            
        try:
            # Extraer región de interés
            h, w = frame.shape[:2]
            x1 = max(0, min(w, self.roi['x1']))
            y1 = max(0, min(h, self.roi['y1']))
            x2 = max(0, min(w, self.roi['x2']))
            y2 = max(0, min(h, self.roi['y2']))
            
            roi = frame[y1:y2, x1:x2]
            if roi.size == 0:
                return None
            
            # Convertir a HSV
            hsv = cv2.cvtColor(roi, cv2.COLOR_BGR2HSV)
            
            # Detectar cada color
            mejor_color = None
            mejor_confianza = 0
            
            for nombre, (rango_bajo, rango_alto) in self.rangos.items():
                # Crear máscara
                mask = cv2.inRange(hsv, rango_bajo, rango_alto)
                
                # Para el rojo, también verificar el rango extendido
                if nombre == 'rojo':
                    mask_extendida = cv2.inRange(hsv, self.rangos_rojo_extendido[0], self.rangos_rojo_extendido[1])
                    mask = cv2.bitwise_or(mask, mask_extendida)
                
                # Calcular área y confianza
                area = cv2.countNonZero(mask)
                total_pixels = roi.shape[0] * roi.shape[1]
                confianza = area / total_pixels if total_pixels > 0 else 0
                
                # Filtrar por área mínima
                if area >= self.area_min and confianza >= self.conf_min:
                    if confianza > mejor_confianza:
                        mejor_confianza = confianza
                        mejor_color = nombre
            
            return mejor_color
            
        except Exception as e:
            logger.debug(f"Error en detección de color: {e}")
            return None


# DRIVER SERIAL TF-LUNA LIDAR DIRECTO (con servo)
class DirectLidar:
    """Manejo serial directo del sensor TF-Luna con control de servo para barrido."""
    def __init__(self, port=PUERTO_LIDAR, baudrate=BAUD_LIDAR):
        self.port = port
        self.baudrate = baudrate
        self.conn = None
        self.servo = None
        self.angulo_actual = ANGULO_FRENTE
        self.conectar()
        self.init_servo()

    def conectar(self):
        try:
            self.conn = serial.Serial(self.port, self.baudrate, timeout=0.02)
            logger.info(f"LiDAR TF-Luna conectado en {self.port}")
        except Exception as e:
            logger.error(f"Error al abrir puerto LiDAR {self.port}: {e}")
            self.conn = None

    def init_servo(self):
        if AngularServo is not None:
            try:
                # gpiozero AngularServo: -90 a +90; convertimos desde 0-180
                # Rango máximo: 0° (izquierda extrema) a 180° (derecha extrema)
                # initial_angle=0 en gpiozero = 0° en gpiozero = 90° en sistema usuario (frente)
                self.servo = AngularServo(PIN_SERVO_LIDAR, min_angle=-90, max_angle=90, initial_angle=0)
                # Centrar explícitamente al frente para asegurar posición correcta
                self.servo.angle = 0  # 0° en gpiozero = 90° en sistema usuario (frente)
                self.angulo_actual = ANGULO_FRENTE
                logger.info(f"Servo LiDAR inicializado en GPIO {PIN_SERVO_LIDAR} (rango 0-180°)")
            except Exception as e:
                logger.warning(f"No se pudo inicializar servo LiDAR: {e}")
                self.servo = None
        else:
            logger.warning("gpiozero no disponible — servo LiDAR deshabilitado")
            self.servo = None

    def apuntar(self, angulo: int):
        """Gira el servo al ángulo indicado (0-180°) con tiempo de asentamiento proporcional."""
        angulo = max(0, min(180, angulo))
        pausa_ms = abs(angulo - self.angulo_actual) * MS_POR_GRADO_SERVO
        pausa_ms = max(60, pausa_ms)  # Mínimo 60 ms
        self.angulo_actual = angulo

        if self.servo:
            try:
                self.servo.angle = angulo - 90  # Convertir 0-180 → -90/+90
                time.sleep(pausa_ms / 1000.0)
            except Exception as e:
                logger.debug(f"Error al mover servo: {e}")

    def leer_distancia_cm(self) -> float:
        """
        Lee el buffer serial y parsea la trama de 9 bytes del TF-Luna.
        Cabecera: 0x59 0x59
        Retorna la distancia en cm o -1.0 si no hay lectura válida.
        """
        if not self.conn or not self.conn.is_open:
            return -1.0

        try:
            bytes_esperando = self.conn.in_waiting
            if bytes_esperando >= 9:
                data = self.conn.read(bytes_esperando)
                for i in range(len(data) - 8 - 1, -1, -1):
                    if data[i] == 0x59 and data[i+1] == 0x59:
                        frame = data[i:i+9]
                        if len(frame) == 9:
                            dist_cm = struct.unpack('<H', frame[2:4])[0]
                            calidad = frame[1]
                            # Calidad > 15 asegura señal real (0 = sin señal)
                            if dist_cm > 0 and calidad > 15:
                                return float(dist_cm)
        except Exception as e:
            logger.debug(f"Error al leer trama LiDAR: {e}")

        return -1.0

    def medir_en(self, angulo: int) -> float:
        """Apunta el servo a un ángulo y retorna la distancia medida."""
        self.apuntar(angulo)
        for _ in range(5):
            d = self.leer_distancia_cm()
            if d > 0:
                return d
            time.sleep(0.01)
        return -1.0

    def cerrar(self):
        if self.conn and self.conn.is_open:
            self.conn.close()
        if self.servo:
            try:
                self.servo.close()
            except Exception:
                pass


# DRIVER SERIAL ARDUINO DIRECTO
class DirectArduino:
    """Envío directo de consignas de velocidad y ángulo al Arduino."""
    def __init__(self, baudrate=BAUD_ARDUINO):
        self.baudrate = baudrate
        self.conn = None
        self.port = self._buscar_puerto()
        self.conectar()

    def _buscar_puerto(self):
        patrones = ['/dev/ttyUSB*', '/dev/ttyACM*']
        for p in patrones:
            puertos = glob.glob(p)
            if puertos:
                return puertos[0]
        return None

    def conectar(self):
        if not self.port:
            logger.warning("No se encontró puerto Arduino automáticamente.")
            return

        try:
            self.conn = serial.Serial(self.port, self.baudrate, timeout=0.1)
            time.sleep(1.8)  # Tiempo de reinicio del bootloader de Arduino
            logger.info(f"Arduino conectado en {self.port}")
        except Exception as e:
            logger.error(f"Error conectando a Arduino en {self.port}: {e}")
            self.conn = None

    def enviar(self, velocidad: int, angulo: int):
        """Envía comando en formato V:<vel>;A:<ang>\n"""
        if not self.conn or not self.conn.is_open:
            logger.warning("Arduino no conectado, no se puede enviar comando")
            return

        velocidad = max(-100, min(100, int(velocidad)))
        angulo = max(10, min(170, int(angulo)))  # Aumentado rango para mayor giro

        comando = f"V:{velocidad};A:{angulo}\n"
        try:
            self.conn.write(comando.encode('utf-8'))
            self.conn.flush()
        except Exception as e:
            logger.error(f"Error enviando comando a Arduino: {e}")

    def frenar(self):
        self.enviar(0, ANGULO_DIRECCION_RECTO)

    def cerrar(self):
        if self.conn and self.conn.is_open:
            self.frenar()
            self.conn.close()


# PROGRAMA PRINCIPAL DE NAVEGACIÓN CON ESQUIVA
class ObstacleRunner:
    # Estados del autómata de navegación
    ESTADO_RECTA = "RECTA"
    ESTADO_ESQUIVANDO = "ESQUIVANDO"
    ESTADO_GIRANDO_ESQUINA = "GIRANDO_ESQUINA"

    def __init__(self):
        logger.info("Inicializando componentes del Sistema de Obstáculos...")
        self.lidar = DirectLidar(PUERTO_LIDAR, BAUD_LIDAR)
        self.arduino = DirectArduino(BAUD_ARDUINO)
        self.boton = None
        
        # Inicializar cámara y detector de colores
        self.camera = CameraStream()
        self.color_detector = ColorDetector()
        self.camera_iniciada = False
        self.color_detectado = None  # 'rojo', 'verde', 'morado' o None
        
        logger.info(f"Configuración cámara: enabled={CAMARA_ENABLED}, {CAMARA_WIDTH}x{CAMARA_HEIGHT} @ {CAMARA_FPS} FPS")
        logger.info(f"Configuración colores: enabled={COLORES_ENABLED}, colores=rojo,verde,morado")

        if Button is not None:
            try:
                self.boton = Button(PIN_BOTON_INICIO, pull_up=True)
                logger.info(f"Pulsador de retención configurado en GPIO {PIN_BOTON_INICIO} (Pin físico 11)")
            except Exception as e:
                logger.warning(f"No se pudo inicializar pulsador de retención: {e}")
                self.boton = None

        self.estado = self.ESTADO_RECTA
        self.esquinas_completadas = 0
        self.tiempo_inicio_maniobra = 0.0
        self.tiempo_ultima_esquina = 0.0
        self.ultima_distancia_valida = 300.0
        self.angulo_esquiva_activo = ANGULO_DIRECCION_RECTO
        self.boton_estado_anterior = None  # Para detectar cambios del switch durante carrera

    def esperar_inicio(self):
        """
        Modo STANDBY tras encendido.
        Espera a que se active el pulsador de retención (toggle switch) físico (Regla WRO 9.11).
        Detecta cualquier cambio de estado del switch (toggle).
        """
        logger.info("==================================================")
        logger.info("[STANDBY] Robot encendido y listo en zona de salida.")

        if self.boton is not None:
            logger.info(f"Esperando activación del pulsador de retención (GPIO {PIN_BOTON_INICIO})...")
            logger.info(f"Estado inicial del switch: {'ON' if not self.boton.is_pressed else 'OFF'}")
            try:
                # Esperar a que el switch cambie de estado (toggle)
                # Con pull_up=True: is_pressed=False = ON, is_pressed=True = OFF
                switch_state = self.boton.is_pressed
                counter = 0
                while True:
                    current_state = self.boton.is_pressed
                    # Log cada 20 iteraciones para no saturar
                    counter += 1
                    if counter % 20 == 0:
                        logger.debug(f"Estado actual del switch: {'ON' if not current_state else 'OFF'}")
                    # Detectar cualquier cambio de estado (toggle)
                    if current_state != switch_state:
                        logger.info(f"¡Switch cambiado de estado! Nuevo estado: {'ON' if not current_state else 'OFF'}. Arrancando en 0.5 segundos...")
                        time.sleep(0.5)
                        return True
                    switch_state = current_state
                    time.sleep(0.05)
            except KeyboardInterrupt:
                logger.info("Cancelado en standby por teclado.")
                return False
        else:
            logger.info("Switch GPIO no disponible. Presione ENTER en consola para iniciar carrera...")
            try:
                input()
                logger.info("¡Comando de inicio recibido! Arrancando en 0.5 segundos...")
                time.sleep(0.5)
                return True
            except (KeyboardInterrupt, EOFError):
                logger.info("Cancelado en standby.")
                return False

    def hacer_barrido_esquiva(self) -> int:
        """
        Mini barrido izquierda/derecha para determinar por qué lado hay más espacio.
        Retorna el ángulo de dirección del carro a aplicar.
        """
        dist_izq = self.lidar.medir_en(ANGULO_IZQUIERDA)
        dist_der = self.lidar.medir_en(ANGULO_DERECHA)
        self.lidar.apuntar(ANGULO_FRENTE)  # Volver al frente

        # Sin señal (-1) se trata como 0 (bloqueado)
        if dist_izq < 0:
            dist_izq = 0.0
        if dist_der < 0:
            dist_der = 0.0

        logger.info(f"[BARRIDO] L:{dist_izq:.0f}cm R:{dist_der:.0f}cm")

        # Decidir dirección basada en color detectado si está disponible
        if self.color_detectado:
            if self.color_detectado == 'rojo':
                # Rojo: esquivar por izquierda
                logger.info(f"[ESQUIVA] ← IZQUIERDA (ROJO) ({ANGULO_GIRO_IZQUIERDA}°)")
                return ANGULO_GIRO_IZQUIERDA
            elif self.color_detectado == 'verde':
                # Verde: esquivar por derecha
                logger.info(f"[ESQUIVA] → DERECHA (VERDE) ({ANGULO_GIRO_DERECHA}°)")
                return ANGULO_GIRO_DERECHA
            elif self.color_detectado == 'morado':
                # Morado: esquivar por izquierda
                logger.info(f"[ESQUIVA] ← IZQUIERDA (MORADO) ({ANGULO_GIRO_IZQUIERDA}°)")
                return ANGULO_GIRO_IZQUIERDA
        
        # Fallback: usar distancia si no hay color detectado
        if dist_izq >= dist_der:
            logger.info(f"[ESQUIVA] ← IZQUIERDA (distancia) ({ANGULO_GIRO_IZQUIERDA}°)")
            return ANGULO_GIRO_IZQUIERDA
        else:
            logger.info(f"[ESQUIVA] → DERECHA (distancia) ({ANGULO_GIRO_DERECHA}°)")
            return ANGULO_GIRO_DERECHA

    def run(self):
        # Loop principal para permitir múltiples carreras con el mismo switch
        while True:
            # 1. Standby hasta botón de inicio
            if not self.esperar_inicio():
                self.limpiar()
                return

            logger.info("=== INICIANDO RETO DE OBSTÁCULOS ===")
            logger.info(f"Meta: {VUELTAS_OBJETIVO} vueltas ({TOTAL_ESQUINAS} esquinas).")

            periodo_bucle = 1.0 / FRECUENCIA_CONTROL_HZ

            # Cooldown inicial: evitar giro falso si arranca cerca de una pared
            self.tiempo_ultima_esquina = time.monotonic()
            
            # Centrar servo antes de iniciar carrera
            logger.info(f"[CENTRAR] Servo a {ANGULO_DIRECCION_RECTO}°")
            self.arduino.enviar(0, ANGULO_DIRECCION_RECTO)
            time.sleep(0.5)
            
            # Inicializar estado del switch para detección durante carrera
            if self.boton is not None:
                self.boton_estado_anterior = self.boton.is_pressed
            
            # Iniciar cámara si está configurada
            if not self.camera_iniciada:
                self.camera_iniciada = self.camera.start()
                if self.camera_iniciada:
                    logger.info("Cámara iniciada para detección de colores")

            try:
                counter = 0
                ultimo_log_estado = 0
                carrera_detenida = False
                while self.esquinas_completadas < TOTAL_ESQUINAS:
                    t_inicio_iter = time.monotonic()
                    ahora = time.monotonic()
                    counter += 1

                    # 1. Leer distancia frontal del LiDAR
                    distancia = self.lidar.leer_distancia_cm()
                    if distancia > 0:
                        self.ultima_distancia_valida = distancia

                    dist = self.ultima_distancia_valida
                    
                    # 1.5. Detectar color del pilar si hay cámara disponible
                    if self.camera_iniciada and counter % 5 == 0:  # Detectar cada 5 ciclos (~0.125s)
                        frame = self.camera.get_latest()
                        if frame:
                            color = self.color_detector.detectar(frame.data)
                            if color and color != self.color_detectado:
                                self.color_detectado = color
                                logger.info(f"[COLOR] Detectado: {color.upper()}")
                            elif not color:
                                self.color_detectado = None

                    # Verificar cambio del switch de inicio (parada de emergencia)
                    if self.boton is not None:
                        boton_estado_actual = self.boton.is_pressed
                        if boton_estado_actual != self.boton_estado_anterior:
                            logger.info("[STOP] Switch de inicio cambiado - Deteniendo carrera")
                            self.boton_estado_anterior = boton_estado_actual
                            carrera_detenida = True
                            break  # Salir del loop de carrera

                    # 2. Máquina de estados de 3 estados
                    if self.estado == self.ESTADO_RECTA:
                        tiempo_desde_esquina = ahora - self.tiempo_ultima_esquina

                        # Prioridad 1: Pared de contención → giro de esquina
                        if dist <= DIST_PARED_ESQUINA_CM and tiempo_desde_esquina >= TIEMPO_COOLDOWN_ESQUINA_SEG:
                            self.estado = self.ESTADO_GIRANDO_ESQUINA
                            self.tiempo_inicio_maniobra = ahora
                            self.tiempo_ultima_esquina = ahora
                            self.esquinas_completadas += 1
                            vueltas = (self.esquinas_completadas - 1) // ESQUINAS_POR_VUELTA
                            esq_en_vuelta = ((self.esquinas_completadas - 1) % ESQUINAS_POR_VUELTA) + 1
                            logger.info(f"[ESQUINA #{self.esquinas_completadas}] V{vueltas+1}-E{esq_en_vuelta} a {dist:.0f}cm")
                            self.arduino.enviar(VELOCIDAD_GIRO, ANGULO_GIRO_DERECHA)

                        # Prioridad 2: Obstáculo (pilar) → barrido y esquiva
                        elif dist <= DIST_OBSTACULO_CM and tiempo_desde_esquina >= TIEMPO_COOLDOWN_ESQUINA_SEG:
                            logger.info(f"[OBSTÁCULO] {dist:.0f}cm - Barrido...")
                            angulo_esquiva = self.hacer_barrido_esquiva()
                            self.angulo_esquiva_activo = angulo_esquiva
                            self.estado = self.ESTADO_ESQUIVANDO
                            self.tiempo_inicio_maniobra = ahora
                            self.arduino.enviar(VELOCIDAD_ESQUIVA, angulo_esquiva)

                        # Prioridad 3: Recta libre
                        else:
                            if ahora - ultimo_log_estado >= 1.0:
                                logger.info(f"[RECTA] {dist:.0f}cm | V:{VELOCIDAD_CRUCERO} A:{ANGULO_DIRECCION_RECTO}")
                                ultimo_log_estado = ahora
                            self.arduino.enviar(VELOCIDAD_CRUCERO, ANGULO_DIRECCION_RECTO)

                    elif self.estado == self.ESTADO_ESQUIVANDO:
                        tiempo_esquivando = ahora - self.tiempo_inicio_maniobra

                        esquiva_completa = False
                        if tiempo_esquivando >= DURACION_MIN_ESQUIVA_SEG:
                            if dist >= DIST_LIBRE_CM or tiempo_esquivando >= DURACION_ESQUIVA_SEG:
                                esquiva_completa = True

                        if esquiva_completa:
                            self.estado = self.ESTADO_RECTA
                            logger.info(f"[FIN ESQUIVA] {tiempo_esquivando:.1f}s | Recta")
                            self.arduino.enviar(VELOCIDAD_CRUCERO, ANGULO_DIRECCION_RECTO)
                        else:
                            self.arduino.enviar(VELOCIDAD_ESQUIVA, self.angulo_esquiva_activo)

                    elif self.estado == self.ESTADO_GIRANDO_ESQUINA:
                        tiempo_girando = ahora - self.tiempo_inicio_maniobra

                        giro_completo = False
                        if tiempo_girando >= DURACION_MIN_GIRO_ESQUINA_SEG:
                            if dist >= DIST_LIBRE_CM or tiempo_girando >= DURACION_MAX_GIRO_ESQUINA_SEG:
                                giro_completo = True

                        if giro_completo:
                            self.estado = self.ESTADO_RECTA
                            logger.info(f"[FIN GIRO] {tiempo_girando:.1f}s | Recta")
                            self.arduino.enviar(VELOCIDAD_CRUCERO, ANGULO_DIRECCION_RECTO)
                        else:
                            self.arduino.enviar(VELOCIDAD_GIRO, ANGULO_GIRO_DERECHA)

                    # Control de frecuencia del bucle
                    t_transcurrido = time.monotonic() - t_inicio_iter
                    t_dormir = periodo_bucle - t_transcurrido
                    if t_dormir > 0:
                        time.sleep(t_dormir)

                if not carrera_detenida:
                    logger.info(f"¡RETO COMPLETADO! Se completaron {TOTAL_ESQUINAS} esquinas ({VUELTAS_OBJETIVO} vueltas).")

            except KeyboardInterrupt:
                logger.info("Interrupción manual por teclado.")
                carrera_detenida = True
            except Exception as e:
                logger.error(f"Error inesperado en loop de obstáculos: {e}", exc_info=True)
                carrera_detenida = True
            
            # Frenar motores después de la carrera (completada o detenida)
            if self.arduino:
                self.arduino.frenar()
                time.sleep(0.1)
            
            # Si la carrera fue detenida por el switch, reiniciar contador para nueva carrera
            if carrera_detenida:
                logger.info("[REINICIO] Carrera detenida por switch - Reiniciando para nueva carrera")
                self.esquinas_completadas = 0
                self.estado = self.ESTADO_RECTA
                time.sleep(1.0)  # Pausa breve antes de volver a standby
            else:
                # Si la carrera se completó normalmente, limpiar y salir del loop
                self.limpiar()
                break

    def limpiar(self):
        logger.info("Deteniendo robot y cerrando conexiones...")
        if self.arduino:
            self.arduino.frenar()
            time.sleep(0.1)
            self.arduino.cerrar()
        if self.lidar:
            self.lidar.cerrar()
        if self.camera:
            self.camera.stop()
        # No cerrar el botón GPIO si estamos en loop principal para múltiples carreras
        # Solo cerrarlo cuando realmente termine el programa
        logger.info("Sistema de obstáculos finalizado con éxito.")


def main():
    runner = ObstacleRunner()
    runner.run()


if __name__ == "__main__":
    main()
