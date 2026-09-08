#!/usr/bin/env python3
"""
SISTEMA DE SEGURIDAD Y NAVEGACIÓN ALTERNATIVO (SAFETY SYSTEM MVP) - WRO 2026
Vehículo: Terreneitor | Categoría: Future Engineers

Comportamiento Dinámico Requerido:
1. Inicia siempre en MODO ABIERTO (reto abierto: navegación por rectas y esquinas).
2. Cámara activa buscando pilares rojo/verde. Al detectar un pilar, cambia a MODO OBSTÁCULOS permanentemente.
3. Auto-detección inteligente del sentido de giro de la pista (Horario / Antihorario) usando el servo SG90 y LiDAR en la primera esquina.
4. Maniobras de esquiva Ackermann en dos fases (evasión + contra-giro de enderezado).
"""

import sys
import time
import glob
import struct
import serial
import logging
import argparse
from typing import Optional, Tuple

# ==============================================================================
# IMPORTS CONDICIONALES DE HARDWARE
# ==============================================================================
try:
    import numpy as np
    import cv2
    VISION_DISPONIBLE = True
except ImportError:
    np = None
    cv2 = None
    VISION_DISPONIBLE = False

try:
    from gpiozero import Button, AngularServo
    GPIO_DISPONIBLE = True
except ImportError:
    Button = None
    AngularServo = None
    GPIO_DISPONIBLE = False

# ==============================================================================
# PARÁMETROS Y CONSTANTES DE COMPETICIÓN
# ==============================================================================

# Pines GPIO (Raspberry Pi BCM)
PIN_BOTON_INICIO = 17       # Switch de retención físico (Pin físico 11)
PIN_SERVO_SCANNER = 18      # Servo SG90 para escaneo ultrasónico (Pin físico 12)
ANGULO_SERVO_CENTRO = 90    # 90° = Centrado frontal
ANGULO_SERVO_DERECHA = 40   # Vista lateral derecha para autodetección
ANGULO_SERVO_IZQUIERDA = 140 # Vista lateral izquierda para autodetección
# Pines para sensor ultrasónico HC-SR04
PIN_ULTRASONICO_TRIGGER = 23  # Pin físico 16
PIN_ULTRASONICO_ECHO = 24     # Pin físico 18

# Puertos Seriales y Velocidades
BAUD_ARDUINO = 115200

# Meta de Carrera
VUELTAS_OBJETIVO = 3
ESQUINAS_POR_VUELTA = 4
TOTAL_ESQUINAS = VUELTAS_OBJETIVO * ESQUINAS_POR_VUELTA
FRECUENCIA_CONTROL_HZ = 40

# Velocidades (-100 a 100)
VEL_CRUCERO = 60
VEL_GIRO = 35
VEL_ESQUIVA = 30

# Ángulos Servo Dirección Arduino (Rango 0 - 270°)
ANG_RECTO = 135
ANG_DERECHA = 0
ANG_IZQUIERDA = 270

# Modos de Competición
MODO_ABIERTO = "ABIERTO"
MODO_OBSTACULOS = "OBSTACULOS"

# Umbrales Sensor Ultrasónico (cm)
DISTANCIA_ESQUINA_CM = 60.0       # Distancia a pared frontal para iniciar giro
DISTANCIA_OBSTACULO_CM = 35.0     # Distancia a pilar para iniciar maniobra esquiva
DISTANCIA_DESPEJADA_CM = 80.0     # Distancia para dar por concluido un giro

# Tiempos de Control (segundos)
DURACION_MIN_GIRO = 0.8
DURACION_MAX_GIRO = 2.2
COOLDOWN_ESQUINA = 1.3
DURACION_ESQUIVA_FASE1 = 0.6      # Giro hacia el lado libre
DURACION_ESQUIVA_FASE2 = 0.6      # Contra-giro para enderezar el chasis
TIMEOUT_LIDAR_FAILSAFE = 1.5

# Configuración Visión / Color HSV
CAMARA_INDEX = 0
CAMARA_WIDTH = 640
CAMARA_HEIGHT = 480
ROI_Y1, ROI_Y2 = 120, 360
ROI_X1, ROI_X2 = 160, 480
AREA_MINIMA_COLOR = 600

HSV_RANGOS = {
    'rojo_1': (np.array([0, 100, 50]), np.array([10, 255, 255])) if VISION_DISPONIBLE else None,
    'rojo_2': (np.array([170, 100, 50]), np.array([180, 255, 255])) if VISION_DISPONIBLE else None,
    'verde':  (np.array([40, 50, 50]),  np.array([85, 255, 255])) if VISION_DISPONIBLE else None,
    'morado': (np.array([130, 50, 50]), np.array([160, 255, 255])) if VISION_DISPONIBLE else None,
}

# Logging
logging.basicConfig(level=logging.INFO, format='%(asctime)s [%(levelname)s] %(message)s')
logger = logging.getLogger("SAFETY_SYS")


# ==============================================================================
# 1. DRIVER SERVO SCANNER SG90 (GPIO 18)
# ==============================================================================

class ServoScanner:
    """Controla el servo SG90 para escanear con el sensor ultrasónico (centrado, izquierda. derecha)."""
    def __init__(self, pin: int = PIN_SERVO_SCANNER, angulo_centro: int = ANGULO_SERVO_CENTRO):
        self.pin = pin
        self.angulo_centro = angulo_centro
        self.servo = None
        self._inicializar()

    def _inicializar(self):
        if not GPIO_DISPONIBLE or AngularServo is None:
            logger.warning("[Servo LiDAR] gpiozero no disponible - modo simulado")
            return
        try:
            self.servo = AngularServo(
                self.pin,
                min_angle=0,
                max_angle=180,
                min_pulse_width=0.0005,
                max_pulse_width=0.0025,
                initial_angle=self.angulo_centro
            )
            logger.info(f"[Servo Scanner] ✓ Inicializado en GPIO {self.pin} (Centro: {self.angulo_centro}°)")
        except Exception as e:
            logger.warning(f"[Servo Scanner] Error al inicializar en GPIO {self.pin}: {e}")
            self.servo = None

    def centrar(self):
        self.mover(self.angulo_centro)

    def mover(self, angulo: float):
        if self.servo:
            try:
                self.servo.angle = max(0.0, min(180.0, float(angulo)))
            except Exception as e:
                logger.debug(f"[Servo LiDAR] Error moviendo servo: {e}")

    def test_movimiento(self):
        logger.info("[Servo Scanner] Probando movimiento (45° -> 135° -> 90°)...")
        for ang in [45, 135, 90]:
            self.mover(ang)
            time.sleep(0.3)

    def cerrar(self):
        if self.servo:
            try:
                self.centrar()
                time.sleep(0.05)
                self.servo.close()
            except Exception:
                pass
            self.servo = None


# ==============================================================================
# 2. DRIVER SENSOR ULTRASÓNICO HC-SR04 (GPIO)
# ==============================================================================

class UltrasonicSensor:
    """Driver para sensor ultrasónico HC-SR04 usando GPIO."""
    def __init__(self, trigger_pin: int = PIN_ULTRASONICO_TRIGGER, echo_pin: int = PIN_ULTRASONICO_ECHO):
        self.trigger_pin = trigger_pin
        self.echo_pin = echo_pin
        self.trigger = None
        self.echo = None
        self.ultima_distancia = 300.0
        self._inicializar()

    def _inicializar(self):
        if not GPIO_DISPONIBLE:
            logger.warning("[Ultrasonido] gpiozero no disponible - modo simulado")
            return
        try:
            from gpiozero import DigitalOutputDevice, InputDevice
            self.trigger = DigitalOutputDevice(self.trigger_pin)
            self.echo = InputDevice(self.echo_pin)
            logger.info(f"[Ultrasonido] ✓ Inicializado en GPIO TRIGGER={self.trigger_pin}, ECHO={self.echo_pin}")
        except Exception as e:
            logger.warning(f"[Ultrasonido] Error al inicializar: {e}")
            self.trigger = None
            self.echo = None

    def leer_distancia_cm(self) -> float:
        """
        Lee distancia usando el sensor ultrasónico HC-SR04.
        Retorna distancia en cm o -1.0 si no hay lectura válida.
        """
        if not self.trigger or not self.echo:
            return -1.0

        try:
            # Enviar pulso trigger
            self.trigger.off()
            time.sleep(0.00001)
            self.trigger.on()
            time.sleep(0.00001)
            self.trigger.off()

            # Medir tiempo de echo
            start_time = time.monotonic()
            timeout = start_time + 0.04  # Timeout 40ms (máximo ~6.8m)
            
            while not self.echo.is_active and time.monotonic() < timeout:
                pass
            
            pulse_start = time.monotonic()
            
            while self.echo.is_active and time.monotonic() < timeout:
                pass
            
            pulse_end = time.monotonic()
            
            pulse_duration = pulse_end - pulse_start
            
            # Calcular distancia: velocidad sonido = 34300 cm/s
            # Distancia = (tiempo * velocidad) / 2 (ida y vuelta)
            distancia = (pulse_duration * 34300) / 2
            
            # Filtrar lecturas inválidas
            if 2.0 <= distancia <= 400.0:  # Rango típico HC-SR04: 2cm a 400cm
                self.ultima_distancia = distancia
                return distancia
            
        except Exception as e:
            logger.debug(f"[Ultrasonido] Error en lectura: {e}")

        return -1.0

    def medir_promedio(self, muestras: int = 3, pausa: float = 0.02) -> float:
        """Toma varias lecturas consecutivas y devuelve el promedio de distancias válidas."""
        lecturas = []
        for _ in range(muestras):
            d = self.leer_distancia_cm()
            if d > 0:
                lecturas.append(d)
            time.sleep(pausa)
        return sum(lecturas)/len(lecturas) if lecturas else -1.0

    def cerrar(self):
        if self.trigger:
            try:
                self.trigger.close()
            except Exception:
                pass
        if self.echo:
            try:
                self.echo.close()
            except Exception:
                pass


# ==============================================================================
# 3. DRIVER SERIAL ARDUINO UNO (COMUNICACIÓN NO BLOQUEANTE)
# ==============================================================================

class ArduinoDriver:
    """Envío y recepción de consignas de dirección y tracción con Arduino UNO."""
    def __init__(self, baudrate: int = BAUD_ARDUINO):
        self.baudrate = baudrate
        self.conn = None
        self.port = self._buscar_puerto()
        self._ultimo_warning = 0.0
        self.conectar()

    def _buscar_puerto(self) -> Optional[str]:
        for pattern in ['/dev/ttyUSB*', '/dev/ttyACM*']:
            puertos = glob.glob(pattern)
            if puertos:
                return puertos[0]
        return None

    def conectar(self):
        if not self.port:
            logger.warning("[Arduino] No se detectó puerto USB/ACM disponible")
            return
        try:
            self.conn = serial.Serial(self.port, self.baudrate, timeout=0.01, write_timeout=0.05)
            time.sleep(1.5)
            self.conn.reset_input_buffer()
            self.conn.reset_output_buffer()
            logger.info(f"[Arduino] ✓ Conectado en {self.port}")
        except Exception as e:
            logger.error(f"[Arduino] ✗ Error de conexión en {self.port}: {e}")
            self.conn = None

    def enviar(self, velocidad: int, angulo: int):
        """Envía comando V:<vel>;A:<ang>\\n."""
        if not self.conn or not self.conn.is_open:
            ahora = time.monotonic()
            if ahora - self._ultimo_warning > 4.0:
                logger.warning("[Arduino] No conectado - Comando no transmitido")
                self._ultimo_warning = ahora
            return

        v = max(-100, min(100, int(velocidad)))
        a = max(0, min(270, int(angulo)))
        cmd = f"V:{v};A:{a}\n".encode('utf-8')
        try:
            self.conn.write(cmd)
            self.conn.flush()
        except Exception as e:
            logger.error(f"[Arduino] Error al escribir comando: {e}")

    def leer_telemetria_no_bloqueante(self) -> Optional[str]:
        if not self.conn or not self.conn.is_open:
            return None
        try:
            if self.conn.in_waiting > 0:
                line = self.conn.readline().decode('utf-8', errors='ignore').strip()
                return line if line else None
        except Exception:
            pass
        return None

    def frenar(self):
        self.enviar(0, ANG_RECTO)

    def cerrar(self):
        if self.conn and self.conn.is_open:
            try:
                self.frenar()
                time.sleep(0.05)
                self.conn.close()
            except Exception:
                pass


# ==============================================================================
# 4. SUBSISTEMA DE VISIÓN Y DETECCIÓN DE COLOR
# ==============================================================================

class VisionColorDetector:
    """Captura y análisis de color HSV optimizado para cámara USB."""
    def __init__(self, camera_index: int = CAMARA_INDEX):
        self.index = camera_index
        self.cap = None
        self.disponible = False
        if VISION_DISPONIBLE:
            self._inicializar()

    def _inicializar(self):
        try:
            self.cap = cv2.VideoCapture(self.index)
            if self.cap.isOpened():
                self.cap.set(cv2.CAP_PROP_FRAME_WIDTH, CAMARA_WIDTH)
                self.cap.set(cv2.CAP_PROP_FRAME_HEIGHT, CAMARA_HEIGHT)
                self.cap.set(cv2.CAP_PROP_BUFFERSIZE, 1)
                self.disponible = True
                logger.info(f"[Cámara] ✓ Iniciada en índice {self.index} ({CAMARA_WIDTH}x{CAMARA_HEIGHT})")
            else:
                logger.warning(f"[Cámara] ✗ No se pudo abrir dispositivo en índice {self.index}")
        except Exception as e:
            logger.warning(f"[Cámara] Error al iniciar VideoCapture: {e}")

    def detectar_color(self) -> Optional[str]:
        """Retorna 'rojo', 'verde', 'morado' o None."""
        if not self.disponible or self.cap is None:
            return None

        try:
            ret, frame = self.cap.read()
            if not ret or frame is None:
                return None

            roi = frame[ROI_Y1:ROI_Y2, ROI_X1:ROI_X2]
            if roi.size == 0:
                return None

            hsv = cv2.cvtColor(roi, cv2.COLOR_BGR2HSV)
            mejor_color = None
            max_area = 0

            # 1. Rojo
            mask_r1 = cv2.inRange(hsv, HSV_RANGOS['rojo_1'][0], HSV_RANGOS['rojo_1'][1])
            mask_r2 = cv2.inRange(hsv, HSV_RANGOS['rojo_2'][0], HSV_RANGOS['rojo_2'][1])
            area_rojo = cv2.countNonZero(cv2.bitwise_or(mask_r1, mask_r2))
            if area_rojo > AREA_MINIMA_COLOR and area_rojo > max_area:
                max_area = area_rojo
                mejor_color = 'rojo'

            # 2. Verde
            mask_v = cv2.inRange(hsv, HSV_RANGOS['verde'][0], HSV_RANGOS['verde'][1])
            area_verde = cv2.countNonZero(mask_v)
            if area_verde > AREA_MINIMA_COLOR and area_verde > max_area:
                max_area = area_verde
                mejor_color = 'verde'

            # 3. Morado
            mask_m = cv2.inRange(hsv, HSV_RANGOS['morado'][0], HSV_RANGOS['morado'][1])
            area_morado = cv2.countNonZero(mask_m)
            if area_morado > AREA_MINIMA_COLOR and area_morado > max_area:
                max_area = area_morado
                mejor_color = 'morado'

            return mejor_color

        except Exception as e:
            logger.debug(f"[Cámara] Error procesando frame: {e}")
            return None

    def cerrar(self):
        if self.cap:
            try:
                self.cap.release()
            except Exception:
                pass


# ==============================================================================
# 5. CONTROLADOR DE NAVEGACIÓN Y MÁQUINA DE ESTADOS (SAFETY RUNNER)
# ==============================================================================

class SafetyRunner:
    """Máquina de Estados WRO con inicio en Reto Abierto, transición dinámica y autodetección de sentido."""
    
    # Estados de navegación interna
    ESTADO_RECTA = "RECTA"
    ESTADO_GIRO_ESQUINA = "GIRO_ESQUINA"
    ESTADO_ESQUIVA_FASE1 = "ESQUIVA_FASE1"
    ESTADO_ESQUIVA_FASE2 = "ESQUIVA_FASE2"

    def __init__(self):
        logger.info("=== Inicializando Safety System (MVP) ===")
        self.ultrasonido = UltrasonicSensor(PIN_ULTRASONICO_TRIGGER, PIN_ULTRASONICO_ECHO)
        self.servo_scanner = ServoScanner(PIN_SERVO_SCANNER, ANGULO_SERVO_CENTRO)
        self.arduino = ArduinoDriver(BAUD_ARDUINO)
        self.vision = VisionColorDetector(CAMARA_INDEX)
        self.boton = None

        if GPIO_DISPONIBLE and Button is not None:
            try:
                self.boton = Button(PIN_BOTON_INICIO, pull_up=True, bounce_time=0.1)
                logger.info(f"[Switch] ✓ Pulsador de retención en GPIO {PIN_BOTON_INICIO}")
            except Exception as e:
                logger.warning(f"[Switch] ✗ Error en GPIO {PIN_BOTON_INICIO}: {e}")

        # Modo de Competición (Inicia siempre en ABIERTO)
        self.modo_competicion = MODO_ABIERTO
        
        # Sentido de Giro (Autodetectado en primera esquina)
        self.sentido_detectado = None
        self.angulo_giro_esquina = ANG_DERECHA  # Por defecto horario hasta autodetección

        # Variables de Carrera
        self.estado = self.ESTADO_RECTA
        self.esquinas_completadas = 0
        self.tiempo_inicio_maniobra = 0.0
        self.tiempo_ultima_esquina = 0.0
        self.distancia_actual = 300.0
        self.tiempo_ultimo_lidar_ok = time.monotonic()
        self.angulo_esquiva_actual = ANG_RECTO
        self.angulo_contra_esquiva = ANG_RECTO

    def autodetectar_sentido_giro(self) -> str:
        """
        Usa el servo SG90 para escanear a derecha e izquierda en la primera esquina
        y determinar si la pista gira en sentido Horario (Derecha) o Antihorario (Izquierda).
        """
        logger.info("[AUTODETECCIÓN] Escaneando apertura lateral de la pista...")
        
        # 1. Medir a la DERECHA
        self.servo_scanner.mover(ANGULO_SERVO_DERECHA)
        time.sleep(0.4)
        dist_der = self.ultrasonido.medir_promedio(muestras=3)
        
        # 2. Medir a la IZQUIERDA
        self.servo_scanner.mover(ANGULO_SERVO_IZQUIERDA)
        time.sleep(0.4)
        dist_izq = self.ultrasonido.medir_promedio(muestras=3)
        
        # 3. Volver de inmediato al centro
        self.servo_scanner.centrar()
        
        logger.info(f"[AUTODETECCIÓN] Lecturas laterales -> Derecha: {dist_der:.0f}cm | Izquierda: {dist_izq:.0f}cm")
        
        # Lado con mayor distancia libre es la dirección de la pista
        if dist_der >= dist_izq:
            sentido = "derecha"
            self.angulo_giro_esquina = ANG_DERECHA
        else:
            sentido = "izquierda"
            self.angulo_giro_esquina = ANG_IZQUIERDA
            
        self.sentido_detectado = sentido
        logger.info(f"[AUTODETECCIÓN] ✓ Sentido confirmado: {sentido.upper()} (Ángulo servo esquina: {self.angulo_giro_esquina}°)")
        return sentido

    def esperar_inicio(self) -> bool:
        """Modo Standby: Centra servo y espera el switch físico o tecla ENTER."""
        logger.info("--------------------------------------------------")
        logger.info("[STANDBY] Robot listo en zona de salida. Esperando señal de arranque...")
        self.servo_scanner.centrar()
        self.arduino.frenar()

        d = self.ultrasonido.leer_distancia_cm()
        if d > 0:
            logger.info(f"[Ultrasonido] ✓ Señal activa: {d:.0f} cm")
        else:
            logger.warning("[Ultrasonido] ⚠️ Esperando primeras lecturas del sensor HC-SR04...")

        if self.boton is not None:
            estado_previo = self.boton.is_pressed
            try:
                while True:
                    estado_actual = self.boton.is_pressed
                    if estado_actual != estado_previo:
                        logger.info("¡Switch activado! Arrancando carrera en 0.5s...")
                        time.sleep(0.5)
                        return True
                    time.sleep(0.05)
            except KeyboardInterrupt:
                return False
        else:
            logger.info("Presione ENTER en consola para iniciar...")
            try:
                input()
                return True
            except (KeyboardInterrupt, EOFError):
                return False

    def _determinar_angulos_esquiva(self, color: str) -> Tuple[int, int]:
        """
        Regla WRO 9.19:
        - Pilar Rojo: Rodear dejándolo a la derecha -> Girar primero a la IZQUIERDA.
        - Pilar Verde: Rodear dejándolo a la izquierda -> Girar primero a la DERECHA.
        """
        if color == 'rojo':
            return (ANG_IZQUIERDA, ANG_DERECHA)
        elif color == 'verde':
            return (ANG_DERECHA, ANG_IZQUIERDA)
        elif color == 'morado':
            return (ANG_IZQUIERDA, ANG_DERECHA)
        else:
            return (ANG_IZQUIERDA, ANG_DERECHA)

    def ciclo_control(self, ahora: float):
        """Ciclo determinista ejecutado a 40 Hz."""
        # 1. Telemetría no bloqueante
        self.arduino.leer_telemetria_no_bloqueante()

        # 2. Lectura Ultrasonido
        d = self.ultrasonido.leer_distancia_cm()
        if d > 0:
            self.distancia_actual = d
            self.tiempo_ultimo_lidar_ok = ahora
        else:
            tiempo_sin_sensor = ahora - self.tiempo_ultimo_lidar_ok
            if tiempo_sin_sensor > TIMEOUT_LIDAR_FAILSAFE:
                logger.warning(f"[FAIL-SAFE] ⚠️ Sin señal ultrasonido por {tiempo_sin_sensor:.1f}s")
                if tiempo_sin_sensor > 4.0:
                    logger.critical("[FAIL-SAFE] ¡Pérdida crítica de sensor! Frenando.")
                    self.arduino.frenar()
                    return

        dist = self.distancia_actual
        tiempo_desde_esquina = ahora - self.tiempo_ultima_esquina

        # 3. Visión y Transición Dinámica de Modo
        color_detectado = self.vision.detectar_color()
        if color_detectado in ['rojo', 'verde', 'morado'] and self.modo_competicion == MODO_ABIERTO:
            self.modo_competicion = MODO_OBSTACULOS
            logger.info(f"╔══════════════════════════════════════════════════════╗")
            logger.info(f"║ [CAMBIO DE MODO] ¡Pilar {color_detectado.upper()} detectado!             ║")
            logger.info(f"║ Transición permanente activada: MODO OBSTÁCULOS      ║")
            logger.info(f"╚══════════════════════════════════════════════════════╝")

        # ==================== MÁQUINA DE ESTADOS ====================

        if self.estado == self.ESTADO_RECTA:
            # Prioridad 1: Obstáculo detectado en Modo Obstáculos
            if self.modo_competicion == MODO_OBSTACULOS and color_detectado is not None and dist <= DISTANCIA_OBSTACULO_CM and tiempo_desde_esquina >= COOLDOWN_ESQUINA:
                self.angulo_esquiva_actual, self.angulo_contra_esquiva = self._determinar_angulos_esquiva(color_detectado)
                self.estado = self.ESTADO_ESQUIVA_FASE1
                self.tiempo_inicio_maniobra = ahora
                logger.info(f"[OBSTÁCULO] Pilar {color_detectado.upper()} a {dist:.0f}cm -> Esquiva Fase 1 ({self.angulo_esquiva_actual}°)")
                self.arduino.enviar(VEL_ESQUIVA, self.angulo_esquiva_actual)

            # Prioridad 2: Pared frontal de esquina
            elif dist <= DISTANCIA_ESQUINA_CM and tiempo_desde_esquina >= COOLDOWN_ESQUINA:
                # Si es la primera esquina, autodetectar sentido de giro con el LiDAR
                if self.sentido_detectado is None:
                    self.arduino.enviar(0, ANG_RECTO)  # Breve pausa para escanear con precisión
                    self.autodetectar_sentido_giro()

                self.estado = self.ESTADO_GIRO_ESQUINA
                self.tiempo_inicio_maniobra = ahora
                self.tiempo_ultima_esquina = ahora
                self.esquinas_completadas += 1
                v = (self.esquinas_completadas - 1) // ESQUINAS_POR_VUELTA + 1
                e = ((self.esquinas_completadas - 1) % ESQUINAS_POR_VUELTA) + 1
                logger.info(f"[ESQUINA #{self.esquinas_completadas}] V{v}-E{e} a {dist:.0f}cm -> Giro {self.sentido_detectado.upper()} ({self.angulo_giro_esquina}°)")
                self.arduino.enviar(VEL_GIRO, self.angulo_giro_esquina)

            # Prioridad 3: Recta libre
            else:
                self.arduino.enviar(VEL_CRUCERO, ANG_RECTO)

        elif self.estado == self.ESTADO_GIRO_ESQUINA:
            tiempo_giro = ahora - self.tiempo_inicio_maniobra
            if (tiempo_giro >= DURACION_MIN_GIRO and dist >= DISTANCIA_DESPEJADA_CM) or (tiempo_giro >= DURACION_MAX_GIRO):
                self.estado = self.ESTADO_RECTA
                logger.info(f"[FIN GIRO] Duración: {tiempo_giro:.1f}s | Retomando recta libre")
                self.arduino.enviar(VEL_CRUCERO, ANG_RECTO)
            else:
                self.arduino.enviar(VEL_GIRO, self.angulo_giro_esquina)

        elif self.estado == self.ESTADO_ESQUIVA_FASE1:
            tiempo_esquiva_1 = ahora - self.tiempo_inicio_maniobra
            if tiempo_esquiva_1 >= DURACION_ESQUIVA_FASE1:
                self.estado = self.ESTADO_ESQUIVA_FASE2
                self.tiempo_inicio_maniobra = ahora
                logger.info(f"[ESQUIVA] Fase 2: Contra-giro de enderezado ({self.angulo_contra_esquiva}°)")
                self.arduino.enviar(VEL_ESQUIVA, self.angulo_contra_esquiva)
            else:
                self.arduino.enviar(VEL_ESQUIVA, self.angulo_esquiva_actual)

        elif self.estado == self.ESTADO_ESQUIVA_FASE2:
            tiempo_esquiva_2 = ahora - self.tiempo_inicio_maniobra
            if tiempo_esquiva_2 >= DURACION_ESQUIVA_FASE2:
                self.estado = self.ESTADO_RECTA
                logger.info(f"[FIN ESQUIVA] Maniobra completada | Retomando recta")
                self.arduino.enviar(VEL_CRUCERO, ANG_RECTO)
            else:
                self.arduino.enviar(VEL_ESQUIVA, self.angulo_contra_esquiva)

    def run(self):
        """Bucle principal de ejecución de carrera."""
        while True:
            if not self.esperar_inicio():
                self.limpiar()
                return

            logger.info("=== INICIANDO CARRERA (WRO SAFETY MVP) ===")
            logger.info(f"Modo inicial: {self.modo_competicion} | Objetivo: {VUELTAS_OBJETIVO} vueltas ({TOTAL_ESQUINAS} esquinas)")

            periodo = 1.0 / FRECUENCIA_CONTROL_HZ
            self.esquinas_completadas = 0
            self.estado = self.ESTADO_RECTA
            self.sentido_detectado = None
            self.modo_competicion = MODO_ABIERTO
            self.tiempo_ultima_esquina = time.monotonic()
            self.tiempo_ultimo_lidar_ok = time.monotonic()
            
            self.servo_scanner.centrar()
            self.arduino.enviar(VEL_CRUCERO, ANG_RECTO)

            boton_estado_previo = self.boton.is_pressed if self.boton else None
            carrera_abortada = False

            try:
                while self.esquinas_completadas < TOTAL_ESQUINAS:
                    t_inicio = time.monotonic()
                    ahora = time.monotonic()

                    # Chequeo de switch de parada de emergencia
                    if self.boton:
                        b_act = self.boton.is_pressed
                        if b_act != boton_estado_previo:
                            logger.info("[STOP] Switch accionado -> Deteniendo carrera")
                            carrera_abortada = True
                            break

                    self.ciclo_control(ahora)

                    t_loop = time.monotonic() - t_inicio
                    t_sleep = periodo - t_loop
                    if t_sleep > 0:
                        time.sleep(t_sleep)

                if not carrera_abortada:
                    logger.info(f"¡CARRERA COMPLETADA! {TOTAL_ESQUINAS} esquinas ({VUELTAS_OBJETIVO} vueltas) concluidas.")

            except KeyboardInterrupt:
                logger.info("Interrupción por teclado.")
                carrera_abortada = True
            except Exception as e:
                logger.error(f"Excepción en carrera: {e}", exc_info=True)
                carrera_abortada = True

            self.arduino.frenar()
            time.sleep(0.2)

            if carrera_abortada:
                logger.info("[REINICIO] Preparando para nueva carrera...")
                time.sleep(1.0)
            else:
                self.limpiar()
                break

    def limpiar(self):
        logger.info("Cerrando subsistemas y liberando hardware...")
        self.arduino.cerrar()
        self.servo_scanner.cerrar()
        self.ultrasonido.cerrar()
        self.vision.cerrar()
        logger.info("Safety System finalizado.")


# ==============================================================================
# AUTODIAGNÓSTICO RÁPIDO DE BANCO (--test)
# ==============================================================================

def autodiagnostico():
    print("=" * 60)
    print("   WRO 2026 - SAFETY SYSTEM HARDWARE SELF-TEST")
    print("=" * 60)

    # 1. Servo Scanner
    print("\n[1/4] Probando Servo SG90 Scanner en GPIO 18...")
    s = ServoScanner()
    s.test_movimiento()
    print("   ✓ Servo centrado a 90°.")

    # 2. Sensor Ultrasónico HC-SR04
    print("\n[2/4] Probando sensor ultrasónico HC-SR04 en GPIO 23/24...")
    ultrasonido = UltrasonicSensor()
    t0 = time.time()
    lecturas = 0
    while time.time() - t0 < 2.5:
        d = ultrasonido.leer_distancia_cm()
        if d > 0:
            lecturas += 1
            print(f"   -> Distancia: {d:5.1f} cm      ", end='\r')
        time.sleep(0.04)
    print()
    if lecturas > 0:
        print(f"   ✓ Ultrasonido operativo ({lecturas} lecturas válidas).")
    else:
        print("   ✗ No se recibieron lecturas válidas de HC-SR04.")

    # 3. Arduino
    print("\n[3/4] Probando Arduino UNO...")
    ard = ArduinoDriver()
    if ard.conn and ard.conn.is_open:
        print(f"   ✓ Conectado en {ard.port}. Probando pulso de dirección...")
        ard.enviar(0, ANG_RECTO)
        time.sleep(0.3)
        ard.enviar(0, ANG_IZQUIERDA)
        time.sleep(0.3)
        ard.enviar(0, ANG_DERECHA)
        time.sleep(0.3)
        ard.enviar(0, ANG_RECTO)
        time.sleep(0.2)
        print("   ✓ Pulsos transmitidos.")
    else:
        print("   ✗ Arduino no detectado.")

    # 4. Cámara
    print("\n[4/4] Probando Cámara...")
    vis = VisionColorDetector()
    if vis.disponible:
        c = vis.detectar_color()
        print(f"   ✓ Cámara operativa. Color en ROI: {c or 'Ninguno (neutro)'}")
    else:
        print("   ✗ Cámara no disponible.")

    # Limpieza
    s.cerrar()
    ultrasonido.cerrar()
    ard.cerrar()
    vis.cerrar()
    print("\n" + "=" * 60)
    print("   TEST COMPLETADO")
    print("=" * 60)


def main():
    parser = argparse.ArgumentParser(description="WRO 2026 Safety System Runner")
    parser.add_argument("--test", "-t", action="store_true", help="Ejecutar autodiagnóstico de hardware")
    args = parser.parse_args()

    if args.test:
        autodiagnostico()
    else:
        runner = SafetyRunner()
        runner.run()


if __name__ == "__main__":
    main()
