#!/usr/bin/env python3
"""
SISTEMA DE EMERGENCIA WRO - Modo Dinámico Unidireccional
Objetivo: Completar 3 vueltas (12 esquinas) al circuito en el menor tiempo posible.

Comportamiento dinámico:
1. Inicia siempre en modo abierto (recta → giro en esquina)
2. Cámara siempre activa buscando colores rojo/verde/morado
3. Al detectar cualquier color, cambia permanentemente a modo obstáculos
4. Una vez en obstáculos, se mantiene hasta completar la carrera
5. Sentido de giro configurable (horario/antihorario) mediante constante SENTIDO_GIRO

Protocolo WRO:
1. Encendido: Inicializa sensores y queda en modo STANDBY.
2. Pulsador de retención: Al cambiar el estado del switch físico (GPIO 17), arranca la carrera.
3. Carrera: Avanza y adapta comportamiento según detección de colores.
4. Finalización: Completa 12 esquinas (3 vueltas), frena y se detiene.
"""

import time
import glob
import struct
import serial
import logging
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
    from gpiozero import Button
except ImportError:
    Button = None

# ==============================================================================
# CONFIGURACIÓN (CONSTANTES)
# ==============================================================================

# Hardware
PIN_BOTON_INICIO = 17

# Conexiones seriales
PUERTO_LIDAR = "/dev/serial0"
BAUD_LIDAR = 115200
BAUD_ARDUINO = 115200

# Parámetros de navegación
VUELTAS_OBJETIVO = 3
ESQUINAS_POR_VUELTA = 4
TOTAL_ESQUINAS = VUELTAS_OBJETIVO * ESQUINAS_POR_VUELTA
FRECUENCIA_CONTROL_HZ = 40

# Velocidades (-100 a 100)
VELOCIDAD_CRUCERO = 65
VELOCIDAD_GIRO = 35
VELOCIDAD_ESQUIVA = 30

# Ángulos del servo de dirección del carro (valores Arduino)
ANGULO_DIRECCION_RECTO = 90
ANGULO_GIRO_DERECHA = 10
ANGULO_GIRO_IZQUIERDA = 170

# Sentido de giro de la pista
SENTIDO_GIRO = "derecha"  # "derecha" para horario, "izquierda" para antihorario

# Determinar ángulo de giro según sentido
if SENTIDO_GIRO == "derecha":
    ANGULO_GIRO_ESQUINA = ANGULO_GIRO_DERECHA
else:
    ANGULO_GIRO_ESQUINA = ANGULO_GIRO_IZQUIERDA

# Umbrales de distancia LiDAR (en cm)
DISTANCIA_GIRO_CM = 85.0
DISTANCIA_OBSTACULO_CM = 50.0
DISTANCIA_DESPEJADA_CM = 110.0

# Tiempos de control
DURACION_MAX_GIRO_SEG = 2.0
DURACION_MIN_GIRO_SEG = 0.8
TIEMPO_COOLDOWN_ESQUINA_SEG = 1.4
DURACION_ESQUIVA_SEG = 1.2
DURACION_MIN_ESQUIVA_SEG = 0.5

# Configuración de cámara
CAMARA_ENABLED = True
CAMARA_WIDTH = 640
CAMARA_HEIGHT = 480
CAMARA_FPS = 30
CAMARA_BUFFER_SIZE = 2

# Configuración de detección de colores
COLORES_ENABLED = True
REGION_INTERES = {'x1': 160, 'y1': 120, 'x2': 480, 'y2': 360}
AREA_MINIMA = 500
CONFIANZA_MINIMA = 0.3

# Rangos HSV para colores
COLOR_ROJO = {'h_min': 0, 'h_max': 10, 's_min': 100, 's_max': 255, 'v_min': 50, 'v_max': 255}
COLOR_VERDE = {'h_min': 40, 'h_max': 80, 's_min': 50, 's_max': 255, 'v_min': 50, 'v_max': 255}
COLOR_MORADO = {'h_min': 130, 'h_max': 160, 's_min': 50, 's_max': 255, 'v_min': 50, 'v_max': 255}

# Estados de navegación
ESTADO_ABIERTO = "ABIERTO"
ESTADO_OBSTACULOS = "OBSTACULOS"

# Estados internos para modo obstáculos
ESTADO_RECTA = "RECTA"
ESTADO_ESQUIVANDO = "ESQUIVANDO"
ESTADO_GIRANDO_ESQUINA = "GIRANDO_ESQUINA"

logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s [%(levelname)s] %(message)s'
)
logger = logging.getLogger("EMERGENCIA_UNIFICADO")

# ==============================================================================
# CLASES DE CÁMARA Y DETECCIÓN DE COLORES
# ==============================================================================

@dataclass
class StampedFrame:
    """Frame con timestamp para sincronización"""
    data: np.ndarray
    timestamp: float
    sequence: int


class CameraStream:
    """Streaming de cámara CSI con thread separado y buffer limitado."""
    
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
            # Backend V4L2 explícito para cámaras CSI (OV5647)
            self._camera = cv2.VideoCapture(0, cv2.CAP_V4L2)
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
        fallos_consecutivos = 0
        ultimo_estado_log = "funcionando"  # Para detectar cambios de estado
        
        while self._running:
            t_start = time.monotonic()
            
            try:
                ret, frame = self._camera.read()
                if not ret or frame is None:
                    fallos_consecutivos += 1
                    
                    # Log solo cuando cambia el estado de funcionando a fallando
                    if fallos_consecutivos == 5 and ultimo_estado_log == "funcionando":
                        logger.warning("[CÁMARA] ✗ Cambio de estado: Dejó de recibir frames (5 fallos consecutivos)")
                        ultimo_estado_log = "fallando"
                    elif fallos_consecutivos == 20 and ultimo_estado_log == "fallando":
                        logger.error("[CÁMARA] ✗✗ Problema persistente: 20 fallos consecutivos - cámara可能 desconectada")
                        ultimo_estado_log = "critico"
                        
                    time.sleep(0.01)
                    continue
                else:
                    # Log solo cuando cambia el estado de fallando a funcionando
                    if fallos_consecutivos > 0 and ultimo_estado_log != "funcionando":
                        logger.info(f"[CÁMARA] ✓ Recuperación: Volvió a recibir frames después de {fallos_consecutivos} fallos")
                        ultimo_estado_log = "funcionando"
                    
                    fallos_consecutivos = 0  # Resetear contador si lectura exitosa
                    
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


class ColorDetector:
    """Detector de colores (rojo, verde, morado) para pilar WRO."""
    
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
        """Detectar el color predominante en la región de interés."""
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

# ==============================================================================
# DRIVER SERIAL TF-LUNA LIDAR DIRECTO (SIN SERVO)
# ==============================================================================

class DirectLidar:
    """Manejo serial directo del sensor TF-Luna sin servo (estático al frente)."""
    def __init__(self, port=PUERTO_LIDAR, baudrate=BAUD_LIDAR):
        self.port = port
        self.baudrate = baudrate
        self.conn = None
        self.conectar()

    def conectar(self):
        try:
            self.conn = serial.Serial(self.port, self.baudrate, timeout=0.02)
            logger.info(f"LiDAR TF-Luna conectado en {self.port}")
        except Exception as e:
            logger.error(f"Error al abrir puerto LiDAR {self.port}: {e}")
            self.conn = None

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
                            if dist_cm > 0 and calidad > 15:
                                return float(dist_cm)
        except Exception as e:
            logger.debug(f"Error al leer trama LiDAR: {e}")

        return -1.0

    def cerrar(self):
        if self.conn and self.conn.is_open:
            self.conn.close()

# ==============================================================================
# DRIVER SERIAL ARDUINO DIRECTO
# ==============================================================================

class DirectArduino:
    """Envío directo de consignas de velocidad y ángulo al Arduino."""
    def __init__(self, baudrate=BAUD_ARDUINO):
        self.baudrate = baudrate
        self.conn = None
        self.port = self._buscar_puerto()
        self.ultimo_warning_conexion = 0.0
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
            time.sleep(1.8)
            logger.info(f"Arduino conectado en {self.port}")
            self.conn.reset_input_buffer()
            self.conn.reset_output_buffer()
        except Exception as e:
            logger.error(f"Error conectando a Arduino en {self.port}: {e}")
            self.conn = None

    def enviar(self, velocidad: int, angulo: int):
        """Envía comando en formato V:<vel>;A:<ang>\n"""
        if not self.conn or not self.conn.is_open:
            ahora = time.monotonic()
            if ahora - self.ultimo_warning_conexion > 5.0:
                logger.warning("Arduino no conectado, no se puede enviar comando")
                self.ultimo_warning_conexion = ahora
            return

        velocidad = max(-100, min(100, int(velocidad)))
        angulo = max(10, min(170, int(angulo)))

        comando = f"V:{velocidad};A:{angulo}\n"
        try:
            self.conn.write(comando.encode('utf-8'))
            self.conn.flush()
        except Exception as e:
            logger.error(f"Error enviando comando a Arduino: {e}")

    def leer_telemetria(self):
        """Lee telemetría del Arduino en formato T:Z:x;A:y;U:z;"""
        if not self.conn or not self.conn.is_open:
            return None

        try:
            if self.conn.in_waiting > 0:
                linea = self.conn.readline().decode('utf-8', errors='ignore').strip()
                if linea:
                    return linea
        except Exception as e:
            logger.debug(f"Error leyendo telemetría: {e}")
        return None

    def frenar(self):
        self.enviar(0, ANGULO_DIRECCION_RECTO)

    def cerrar(self):
        if self.conn and self.conn.is_open:
            self.frenar()
            self.conn.close()

# ==============================================================================
# PROGRAMA PRINCIPAL DE NAVEGACIÓN UNIFICADA
# ==============================================================================

class EmergencyRunner:
    def __init__(self):
        logger.info("Inicializando componentes del Sistema de Emergencia Unificado...")
        self.lidar = DirectLidar(PUERTO_LIDAR, BAUD_LIDAR)
        self.arduino = DirectArduino(BAUD_ARDUINO)
        self.camera = CameraStream()
        self.color_detector = ColorDetector()
        self.boton = None

        # Inicializar Botón de Inicio físico (GPIO 17)
        if Button is not None:
            try:
                self.boton = Button(PIN_BOTON_INICIO, pull_up=True)
                logger.info(f"Pulsador de retención configurado en GPIO {PIN_BOTON_INICIO} (Pin físico 11)")
            except Exception as e:
                logger.warning(f"No se pudo inicializar pulsador de retención: {e}")
                self.boton = None

        # Estado de navegación (modo dinámico)
        self.modo_actual = ESTADO_ABIERTO  # Siempre inicia en modo abierto
        self.color_detectado = None
        self.transicion_a_obstaculos = False

        # Variables de navegación compartidas
        self.esquinas_completadas = 0
        self.tiempo_ultima_esquina = 0.0
        self.ultima_distancia_valida = 300.0
        self.boton_estado_anterior = None
        self.ultima_distancia_log = 0.0

        # Variables específicas para modo abierto
        self.en_giro = False
        self.tiempo_inicio_giro = 0.0

        # Variables específicas para modo obstáculos
        self.estado_obstaculos = ESTADO_RECTA
        self.tiempo_inicio_maniobra = 0.0
        self.angulo_esquiva_activo = ANGULO_DIRECCION_RECTO

        self.camera_iniciada = False

    def esperar_inicio(self):
        """
        Modo STANDBY tras encendido.
        Espera a que se active el pulsador de retención (toggle switch) físico (Regla WRO 9.11).
        """
        logger.info("==================================================")
        logger.info("[STANDBY] Robot encendido y listo en zona de salida.")

        # Iniciar cámara en standby para diagnóstico temprano
        if not self.camera_iniciada:
            self.camera_iniciada = self.camera.start()
            if self.camera_iniciada:
                # Verificar que la cámara está enviando frames
                time.sleep(0.5)  # Dar tiempo para que capture algunos frames
                test_frame = self.camera.get_latest()
                if test_frame:
                    logger.info(f"[CÁMARA] ✓ Conectada y operativa - Recibiendo frames (Seq: {test_frame.sequence})")
                else:
                    logger.warning("[CÁMARA] ✗ Conectada pero no envía frames - Revisar conexión")
            else:
                logger.warning("[CÁMARA] ✗ No disponible - Modo degradado sin detección de colores")

        if self.boton is not None:
            logger.info(f"Esperando activación del pulsador de retención (GPIO {PIN_BOTON_INICIO})...")
            logger.info(f"Estado inicial del switch: {'ON' if not self.boton.is_pressed else 'OFF'}")
            try:
                switch_state = self.boton.is_pressed
                while True:
                    current_state = self.boton.is_pressed
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

    def ejecutar_logica_abierta(self, distancia: float, ahora: float):
        """Lógica de navegación para modo abierto (sin obstáculos)."""
        if not self.en_giro:
            tiempo_desde_ultimo_giro = ahora - self.tiempo_ultima_esquina
            if distancia <= DISTANCIA_GIRO_CM and tiempo_desde_ultimo_giro >= TIEMPO_COOLDOWN_ESQUINA_SEG:
                self.en_giro = True
                self.tiempo_inicio_giro = ahora
                self.tiempo_ultima_esquina = ahora
                self.esquinas_completadas += 1
                vueltas = (self.esquinas_completadas - 1) // ESQUINAS_POR_VUELTA
                esq_en_vuelta = ((self.esquinas_completadas - 1) % ESQUINAS_POR_VUELTA) + 1
                
                logger.info(f"[ESQUINA #{self.esquinas_completadas}] V{vueltas+1}-E{esq_en_vuelta} a {distancia:.0f}cm")
                self.arduino.enviar(VELOCIDAD_GIRO, ANGULO_GIRO_ESQUINA)
            else:
                cambio_distancia = abs(distancia - self.ultima_distancia_log)
                if cambio_distancia > 10.0:
                    logger.info(f"[RECTA] {distancia:.0f}cm | V:{VELOCIDAD_CRUCERO} A:{ANGULO_DIRECCION_RECTO}")
                    self.ultima_distancia_log = distancia
                self.arduino.enviar(VELOCIDAD_CRUCERO, ANGULO_DIRECCION_RECTO)
        else:
            tiempo_en_giro = ahora - self.tiempo_inicio_giro
            giro_completado = False
            if tiempo_en_giro >= DURACION_MIN_GIRO_SEG:
                if distancia >= DISTANCIA_DESPEJADA_CM or tiempo_en_giro >= DURACION_MAX_GIRO_SEG:
                    giro_completado = True

            if giro_completado:
                self.en_giro = False
                logger.info(f"[FIN GIRO] {tiempo_en_giro:.1f}s | Recta")
                self.arduino.enviar(VELOCIDAD_CRUCERO, ANGULO_DIRECCION_RECTO)
            else:
                self.arduino.enviar(VELOCIDAD_GIRO, ANGULO_GIRO_ESQUINA)

    def ejecutar_logica_obstaculos(self, distancia: float, ahora: float):
        """Lógica de navegación para modo obstáculos (con esquiva)."""
        if self.estado_obstaculos == ESTADO_RECTA:
            tiempo_desde_esquina = ahora - self.tiempo_ultima_esquina

            # Prioridad 1: Pared de contención → giro de esquina
            if distancia <= DISTANCIA_GIRO_CM and tiempo_desde_esquina >= TIEMPO_COOLDOWN_ESQUINA_SEG:
                self.estado_obstaculos = ESTADO_GIRANDO_ESQUINA
                self.tiempo_inicio_maniobra = ahora
                self.tiempo_ultima_esquina = ahora
                self.esquinas_completadas += 1
                vueltas = (self.esquinas_completadas - 1) // ESQUINAS_POR_VUELTA
                esq_en_vuelta = ((self.esquinas_completadas - 1) % ESQUINAS_POR_VUELTA) + 1
                logger.info(f"[ESQUINA #{self.esquinas_completadas}] V{vueltas+1}-E{esq_en_vuelta} a {distancia:.0f}cm")
                self.arduino.enviar(VELOCIDAD_GIRO, ANGULO_GIRO_ESQUINA)

            # Prioridad 2: Obstáculo (pilar) → esquiva por color
            elif distancia <= DISTANCIA_OBSTACULO_CM and tiempo_desde_esquina >= TIEMPO_COOLDOWN_ESQUINA_SEG:
                logger.info(f"[OBSTÁCULO] {distancia:.0f}cm - Detectando color...")
                
                # Determinar dirección de esquiva basada en color
                if self.color_detectado == 'rojo':
                    angulo_esquiva = ANGULO_GIRO_IZQUIERDA
                    logger.info(f"[ESQUIVA] ← IZQUIERDA (ROJO) ({angulo_esquiva}°)")
                elif self.color_detectado == 'verde':
                    angulo_esquiva = ANGULO_GIRO_DERECHA
                    logger.info(f"[ESQUIVA] → DERECHA (VERDE) ({angulo_esquiva}°)")
                elif self.color_detectado == 'morado':
                    angulo_esquiva = ANGULO_GIRO_IZQUIERDA
                    logger.info(f"[ESQUIVA] ← IZQUIERDA (MORADO) ({angulo_esquiva}°)")
                else:
                    # Fallback: esquiva izquierda si no detecta color
                    angulo_esquiva = ANGULO_GIRO_IZQUIERDA
                    logger.info(f"[ESQUIVA] ← IZQUIERDA (FALLBACK - sin color) ({angulo_esquiva}°)")
                
                self.angulo_esquiva_activo = angulo_esquiva
                self.estado_obstaculos = ESTADO_ESQUIVANDO
                self.tiempo_inicio_maniobra = ahora
                self.arduino.enviar(VELOCIDAD_ESQUIVA, angulo_esquiva)

            # Prioridad 3: Recta libre
            else:
                logger.info(f"[RECTA] {distancia:.0f}cm | V:{VELOCIDAD_CRUCERO} A:{ANGULO_DIRECCION_RECTO}")
                self.arduino.enviar(VELOCIDAD_CRUCERO, ANGULO_DIRECCION_RECTO)

        elif self.estado_obstaculos == ESTADO_ESQUIVANDO:
            tiempo_esquivando = ahora - self.tiempo_inicio_maniobra
            esquiva_completa = False
            if tiempo_esquivando >= DURACION_MIN_ESQUIVA_SEG:
                if distancia >= DISTANCIA_DESPEJADA_CM or tiempo_esquivando >= DURACION_ESQUIVA_SEG:
                    esquiva_completa = True

            if esquiva_completa:
                self.estado_obstaculos = ESTADO_RECTA
                logger.info(f"[FIN ESQUIVA] {tiempo_esquivando:.1f}s | Recta")
                self.arduino.enviar(VELOCIDAD_CRUCERO, ANGULO_DIRECCION_RECTO)
            else:
                self.arduino.enviar(VELOCIDAD_ESQUIVA, self.angulo_esquiva_activo)

        elif self.estado_obstaculos == ESTADO_GIRANDO_ESQUINA:
            tiempo_girando = ahora - self.tiempo_inicio_maniobra
            giro_completo = False
            if tiempo_girando >= DURACION_MIN_GIRO_SEG:
                if distancia >= DISTANCIA_DESPEJADA_CM or tiempo_girando >= DURACION_MAX_GIRO_SEG:
                    giro_completo = True

            if giro_completo:
                self.estado_obstaculos = ESTADO_RECTA
                logger.info(f"[FIN GIRO] {tiempo_girando:.1f}s | Recta")
                self.arduino.enviar(VELOCIDAD_CRUCERO, ANGULO_DIRECCION_RECTO)
            else:
                self.arduino.enviar(VELOCIDAD_GIRO, ANGULO_GIRO_ESQUINA)

    def run(self):
        # Loop principal para permitir múltiples carreras con el mismo switch
        while True:
            # 1. Modo Standby tras encendido
            if not self.esperar_inicio():
                self.limpiar()
                return

            logger.info("=== INICIANDO NAVEGACIÓN DE EMERGENCIA (MODO DINÁMICO) ===")
            logger.info(f"Meta: {VUELTAS_OBJETIVO} vueltas ({TOTAL_ESQUINAS} esquinas).")
            logger.info(f"Modo inicial: {self.modo_actual}")
            logger.info(f"Umbral de giro frontal: {DISTANCIA_GIRO_CM} cm.")
            logger.info(f"Velocidad crucero: {VELOCIDAD_CRUCERO}, Ángulo recto: {ANGULO_DIRECCION_RECTO}")

            periodo_bucle = 1.0 / FRECUENCIA_CONTROL_HZ

            # Cooldown inicial
            self.tiempo_ultima_esquina = time.monotonic()
            
            # Centrar servo antes de iniciar carrera
            logger.info(f"[CENTRAR] Servo a {ANGULO_DIRECCION_RECTO}°")
            self.arduino.enviar(0, ANGULO_DIRECCION_RECTO)
            time.sleep(0.5)
            
            # Inicializar estado del switch
            if self.boton is not None:
                self.boton_estado_anterior = self.boton.is_pressed
            
            # Iniciar cámara
            if not self.camera_iniciada:
                self.camera_iniciada = self.camera.start()
                if self.camera_iniciada:
                    logger.info("Cámara iniciada para detección dinámica de modo")

            # Enviar comando inicial
            logger.info(f"[ARRANQUE] Vel: {VELOCIDAD_CRUCERO}, Ang: {ANGULO_DIRECCION_RECTO}°")
            self.arduino.enviar(VELOCIDAD_CRUCERO, ANGULO_DIRECCION_RECTO)

            carrera_detenida = False
            try:
                counter = 0
                while self.esquinas_completadas < TOTAL_ESQUINAS:
                    t_inicio_iter = time.monotonic()
                    ahora = time.monotonic()
                    counter += 1

                    # Leer telemetría del Arduino
                    self.arduino.leer_telemetria()

                    # Verificar cambio del switch de inicio
                    if self.boton is not None:
                        boton_estado_actual = self.boton.is_pressed
                        if boton_estado_actual != self.boton_estado_anterior:
                            logger.info("[STOP] Switch de inicio cambiado - Deteniendo carrera")
                            self.boton_estado_anterior = boton_estado_actual
                            carrera_detenida = True
                            break

                    # Leer distancia frontal del LiDAR
                    distancia = self.lidar.leer_distancia_cm()
                    if distancia > 0:
                        self.ultima_distancia_valida = distancia

                    dist = self.ultima_distancia_valida
                    
                    # Detectar color (cada 5 ciclos ~0.125s)
                    if self.camera_iniciada and counter % 5 == 0:
                        frame = self.camera.get_latest()
                        if frame:
                            color = self.color_detector.detectar(frame.data)
                            if color and color != self.color_detectado:
                                self.color_detectado = color
                                logger.info(f"[COLOR] ✓ Confirmado: {color.upper()} detectado")
                            elif not color and self.color_detectado is not None:
                                # Log solo cuando deja de detectar un color que antes detectaba
                                logger.info(f"[COLOR] ✗ Ya no se detecta {self.color_detectado.upper()}")
                                self.color_detectado = None
                        elif self.color_detectado is not None:
                            # Log solo cuando hay frame pero no detecta color esperado
                            logger.debug("[CÁMARA] Frame recibido pero sin color detectado")

                    # Detectar transición a modo obstáculos
                    if not self.transicion_a_obstaculos and self.color_detectado in ['rojo', 'verde', 'morado']:
                        self.transicion_a_obstaculos = True
                        self.modo_actual = ESTADO_OBSTACULOS
                        logger.info(f"[CAMBIO MODO] Detectado {self.color_detectado.upper()} → OBSTACULOS")

                    # Ejecutar lógica según modo actual
                    if self.modo_actual == ESTADO_ABIERTO:
                        self.ejecutar_logica_abierta(dist, ahora)
                    else:
                        self.ejecutar_logica_obstaculos(dist, ahora)

                    # Control de frecuencia
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
                logger.error(f"Error inesperado en loop de emergencia: {e}", exc_info=True)
                carrera_detenida = True
            
            # Frenar motores después de la carrera
            if self.arduino:
                self.arduino.frenar()
                time.sleep(0.1)
            
            # Si la carrera fue detenida por el switch, reiniciar
            if carrera_detenida:
                logger.info("[REINICIO] Carrera detenida por switch - Reiniciando para nueva carrera")
                self.esquinas_completadas = 0
                self.en_giro = False
                self.estado_obstaculos = ESTADO_RECTA
                self.modo_actual = ESTADO_ABIERTO
                self.transicion_a_obstaculos = False
                self.color_detectado = None
                time.sleep(1.0)
            else:
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
        logger.info("Sistema de emergencia unificado finalizado con éxito.")


def main():
    runner = EmergencyRunner()
    runner.run()


if __name__ == "__main__":
    main()
