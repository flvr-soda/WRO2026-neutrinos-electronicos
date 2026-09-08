#!/usr/bin/env python3
"""
SISTEMA DE SEGURIDAD WRO - Sensor Ultrasónico
Objetivo: Navegación autónoma con autodetección de sentido y esquiva de pilares.

Funcionalidades:
- Autodetección de sentido de giro usando servo SG90 + ultrasónico frontal
- Conteo de esquinas por detección de muro a 85cm
- Ángulo de giro máximo posible
- Velocidad 60% en rectas, 35% en giros
- Cámara activa para detección de pilares rojo/verde
- Esquiva: verde → izquierda, rojo → derecha
- Ultrasónico trasero para retroceso seguro (5cm)
"""

import time
import serial
import logging
import os
import sys
import glob

# Configurar pin factory RPi.GPIO
os.environ['GPIOZERO_PIN_FACTORY'] = 'rpigpio'

try:
    from gpiozero import Button, AngularServo, DigitalOutputDevice, InputDevice
except ImportError:
    Button = None
    AngularServo = None
    DigitalOutputDevice = None
    InputDevice = None

try:
    import cv2
    import numpy as np
    VISION_DISPONIBLE = True
except ImportError:
    cv2 = None
    np = None
    VISION_DISPONIBLE = False

# ==============================================================================
# CONFIGURACIÓN
# ==============================================================================

# Pines GPIO
PIN_BOTON_INICIO = 17
PIN_SERVO_SCANNER = 18
PIN_ULTRASONICO_FRONTAL_TRIGGER = 23
PIN_ULTRASONICO_FRONTAL_ECHO = 24
PIN_ULTRASONICO_TRASERO_TRIGGER = 5
PIN_ULTRASONICO_TRASERO_ECHO = 6

# Parámetros de navegación
VUELTAS_OBJETIVO = 3
ESQUINAS_POR_VUELTA = 4
TOTAL_ESQUINAS = VUELTAS_OBJETIVO * ESQUINAS_POR_VUELTA

# Velocidades (0-100)
VELOCIDAD_RECTA = 60
VELOCIDAD_GIRO = 35

# Ángulos servo dirección Arduino
ANGULO_RECTO = 90
ANGULO_GIRO_MAXIMO_DERECHA = 0
ANGULO_GIRO_MAXIMO_IZQUIERDA = 180

# Ángulos servo escaneo
ANGULO_SERVO_CENTRO = 90
ANGULO_SERVO_DERECHA = 40
ANGULO_SERVO_IZQUIERDA = 140

# Umbrales distancia (cm)
DISTANCIA_ESQUINA_CM = 85.0
DISTANCIA_RETROCESO_CM = 5.0

# Tiempos
DURACION_GIRO_SEG = 1.5
COOLDOWN_ESQUINA_SEG = 1.5
TIEMPO_PANEO_SEG = 0.4

# Colores HSV (rojo y verde)
RANGOS_COLOR = {
    'rojo': [(np.array([0, 100, 100]), np.array([10, 255, 255])) if VISION_DISPONIBLE else None,
             (np.array([170, 100, 100]), np.array([180, 255, 255])) if VISION_DISPONIBLE else None],
    'verde': [(np.array([40, 50, 50]), np.array([85, 255, 255])) if VISION_DISPONIBLE else None]
}

# Arduino
BAUD_ARDUINO = 115200

# Logging
logging.basicConfig(level=logging.INFO, format='%(asctime)s [%(levelname)s] %(message)s')
logger = logging.getLogger("SAFETY_ULTRASONICO")

# ==============================================================================
# DRIVER SERVO SCANNER
# ==============================================================================

class ServoScanner:
    """Controla servo SG90 para escaneo lateral con ultrasónico."""
    def __init__(self, pin=PIN_SERVO_SCANNER, angulo_centro=ANGULO_SERVO_CENTRO):
        self.pin = pin
        self.angulo_centro = angulo_centro
        self.servo = None
        self._inicializar()

    def _inicializar(self):
        if AngularServo is None:
            logger.warning("[Servo Scanner] gpiozero no disponible")
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
            logger.info(f"[Servo Scanner] ✓ Inicializado en GPIO {self.pin}")
        except Exception as e:
            logger.warning(f"[Servo Scanner] Error: {e}")
            self.servo = None

    def centrar(self):
        self.mover(self.angulo_centro)

    def mover(self, angulo):
        if self.servo:
            try:
                self.servo.angle = max(0.0, min(180.0, float(angulo)))
            except Exception as e:
                logger.debug(f"[Servo Scanner] Error moviendo: {e}")

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
# DRIVER SENSOR ULTRASÓNICO
# ==============================================================================

class UltrasonicSensor:
    """Driver para sensor ultrasónico HC-SR04."""
    def __init__(self, trigger_pin, echo_pin, nombre="Ultrasonido"):
        self.trigger_pin = trigger_pin
        self.echo_pin = echo_pin
        self.nombre = nombre
        self.trigger = None
        self.echo = None
        self.ultima_distancia = 300.0
        self._inicializar()

    def _inicializar(self):
        if DigitalOutputDevice is None or InputDevice is None:
            logger.warning(f"[{self.nombre}] gpiozero no disponible")
            return
        try:
            self.trigger = DigitalOutputDevice(self.trigger_pin)
            self.echo = InputDevice(self.echo_pin)
            logger.info(f"[{self.nombre}] ✓ Inicializado TRIGGER={self.trigger_pin}, ECHO={self.echo_pin}")
        except Exception as e:
            logger.warning(f"[{self.nombre}] Error: {e}")
            self.trigger = None
            self.echo = None

    def leer_distancia_cm(self):
        if not self.trigger or not self.echo:
            return -1.0

        try:
            self.trigger.off()
            time.sleep(0.00001)
            self.trigger.on()
            time.sleep(0.00001)
            self.trigger.off()

            start_time = time.monotonic()
            timeout = start_time + 0.04
            
            while not self.echo.is_active and time.monotonic() < timeout:
                pass
            
            pulse_start = time.monotonic()
            
            while self.echo.is_active and time.monotonic() < timeout:
                pass
            
            pulse_end = time.monotonic()
            
            pulse_duration = pulse_end - pulse_start
            distancia = (pulse_duration * 34300) / 2
            
            if 2.0 <= distancia <= 400.0:
                self.ultima_distancia = distancia
                return distancia
            
        except Exception as e:
            logger.debug(f"[{self.nombre}] Error: {e}")

        return -1.0

    def medir_promedio(self, muestras=3, pausa=0.02):
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
# DRIVER ARDUINO
# ==============================================================================

class ArduinoDriver:
    """Control de motores vía Arduino."""
    def __init__(self, baudrate=BAUD_ARDUINO):
        self.baudrate = baudrate
        self.conn = None
        self.port = self._buscar_puerto()
        self.conectar()

    def _buscar_puerto(self):
        puertos = glob.glob('/dev/ttyUSB*') + glob.glob('/dev/ttyACM*')
        if puertos:
            return puertos[0]
        return '/dev/ttyUSB0'

    def conectar(self):
        try:
            self.conn = serial.Serial(self.port, self.baudrate, timeout=0.01)
            logger.info(f"[Arduino] ✓ Conectado en {self.port}")
        except Exception as e:
            logger.warning(f"[Arduino] Error al conectar: {e}")
            self.conn = None

    def enviar(self, velocidad, angulo):
        if self.conn and self.conn.is_open:
            try:
                comando = f"{velocidad},{angulo}\n"
                logger.info(f"[Arduino] Enviando: {comando.strip()}")
                self.conn.write(comando.encode())
            except Exception as e:
                logger.warning(f"[Arduino] Error enviando: {e}")

    def frenar(self):
        self.enviar(0, ANGULO_RECTO)

    def cerrar(self):
        if self.conn and self.conn.is_open:
            try:
                self.frenar()
                time.sleep(0.1)
                self.conn.close()
            except Exception:
                pass

# ==============================================================================
# DETECTOR DE COLOR
# ==============================================================================

class ColorDetector:
    """Detección de pilares rojo/verde con OpenCV."""
    def __init__(self, camara_index=0):
        self.camara_index = camara_index
        self.cap = None
        self.disponible = False
        self._inicializar()

    def _inicializar(self):
        if not VISION_DISPONIBLE:
            logger.warning("[Visión] OpenCV no disponible")
            return
        try:
            self.cap = cv2.VideoCapture(self.camara_index)
            if self.cap.isOpened():
                self.disponible = True
                logger.info("[Visión] ✓ Cámara inicializada")
            else:
                logger.warning("[Visión] No se pudo abrir cámara")
        except Exception as e:
            logger.warning(f"[Visión] Error: {e}")

    def detectar_color(self):
        if not self.disponible or self.cap is None:
            return None

        try:
            ret, frame = self.cap.read()
            if not ret:
                return None

            hsv = cv2.cvtColor(frame, cv2.COLOR_BGR2HSV)
            
            # Detectar rojo
            for lower, upper in RANGOS_COLOR['rojo']:
                if lower is not None and upper is not None:
                    mask = cv2.inRange(hsv, lower, upper)
                    if cv2.countNonZero(mask) > 500:
                        return 'rojo'
            
            # Detectar verde
            for lower, upper in RANGOS_COLOR['verde']:
                if lower is not None and upper is not None:
                    mask = cv2.inRange(hsv, lower, upper)
                    if cv2.countNonZero(mask) > 500:
                        return 'verde'
            
        except Exception as e:
            logger.debug(f"[Visión] Error: {e}")

        return None

    def cerrar(self):
        if self.cap:
            try:
                self.cap.release()
            except Exception:
                pass

# ==============================================================================
# SISTEMA PRINCIPAL
# ==============================================================================

class SafetyUltrasonico:
    def __init__(self):
        logger.info("=== Inicializando Sistema Safety Ultrasónico ===")
        self.servo_scanner = ServoScanner()
        self.ultrasonico_frontal = UltrasonicSensor(PIN_ULTRASONICO_FRONTAL_TRIGGER, PIN_ULTRASONICO_FRONTAL_ECHO, "Ultrasonido Frontal")
        self.ultrasonico_trasero = UltrasonicSensor(PIN_ULTRASONICO_TRASERO_TRIGGER, PIN_ULTRASONICO_TRASERO_ECHO, "Ultrasonico Trasero")
        self.arduino = ArduinoDriver()
        self.vision = ColorDetector()
        self.boton = None

        if Button is not None:
            try:
                self.boton = Button(PIN_BOTON_INICIO, pull_up=True)
                logger.info(f"[Botón] ✓ Configurado en GPIO {PIN_BOTON_INICIO}")
            except Exception as e:
                logger.warning(f"[Botón] Error: {e}")

        # Estado
        self.esquinas_completadas = 0
        self.sentido_giro = None  # 'derecha' o 'izquierda'
        self.angulo_giro = None
        self.en_giro = False
        self.tiempo_ultima_esquina = 0.0
        self.en_esquiva = False
        self.color_detectado = None
        self.boton_estado_anterior = None  # Para detectar cambios durante carrera

    def autodetectar_sentido_giro(self):
        """Paneo lateral para detectar dirección de la pista."""
        logger.info("[AUTODETECCIÓN] Escaneando dirección de la pista...")
        
        # Medir derecha
        self.servo_scanner.mover(ANGULO_SERVO_DERECHA)
        time.sleep(TIEMPO_PANEO_SEG)
        dist_der = self.ultrasonico_frontal.medir_promedio(muestras=3)
        
        # Medir izquierda
        self.servo_scanner.mover(ANGULO_SERVO_IZQUIERDA)
        time.sleep(TIEMPO_PANEO_SEG)
        dist_izq = self.ultrasonico_frontal.medir_promedio(muestras=3)
        
        # Volver al centro
        self.servo_scanner.centrar()
        
        logger.info(f"[AUTODETECCIÓN] Derecha: {dist_der:.0f}cm | Izquierda: {dist_izq:.0f}cm")
        
        if dist_der >= dist_izq:
            self.sentido_giro = 'derecha'
            self.angulo_giro = ANGULO_GIRO_MAXIMO_DERECHA
        else:
            self.sentido_giro = 'izquierda'
            self.angulo_giro = ANGULO_GIRO_MAXIMO_IZQUIERDA
        
        logger.info(f"[AUTODETECCIÓN] ✓ Sentido: {self.sentido_giro.upper()} (Ángulo: {self.angulo_giro}°)")
        return self.sentido_giro

    def esquiva_pilar(self, color):
        """Esquiva pilar según color."""
        logger.info(f"[ESQUIVA] Pilar {color} detectado")
        self.en_esquiva = True
        
        if color == 'verde':
            # Esquivar hacia la izquierda
            logger.info("[ESQUIVA] Girando a la izquierda...")
            self.arduino.enviar(VELOCIDAD_GIRO, ANGULO_GIRO_MAXIMO_IZQUIERDA)
            time.sleep(0.8)
            self.arduino.enviar(VELOCIDAD_RECTA, ANGULO_RECTO)
        elif color == 'rojo':
            # Esquivar hacia la derecha
            logger.info("[ESQUIVA] Girando a la derecha...")
            self.arduino.enviar(VELOCIDAD_GIRO, ANGULO_GIRO_MAXIMO_DERECHA)
            time.sleep(0.8)
            self.arduino.enviar(VELOCIDAD_RECTA, ANGULO_RECTO)
        
        self.en_esquiva = False

    def retroceso_seguro(self):
        """Retrocede si ultrasónico trasero detecta obstáculo a 5cm."""
        dist_trasera = self.ultrasonico_trasero.leer_distancia_cm()
        if dist_trasera > 0 and dist_trasera < DISTANCIA_RETROCESO_CM:
            logger.warning(f"[RETROCESO] Obstáculo trasero a {dist_trasera:.0f}cm")
            self.arduino.enviar(-30, ANGULO_RECTO)  # Velocidad negativa para retroceder
            time.sleep(0.5)
            self.arduino.frenar()
            return True
        return False

    def esperar_inicio(self):
        """Espera activación del botón - requiere cambio de estado."""
        logger.info("==================================================")
        logger.info("[STANDBY] Esperando activación del botón...")
        
        if self.boton is not None:
            self.boton_estado_anterior = self.boton.is_pressed
            logger.info(f"Estado inicial: {'ON' if not self.boton.is_pressed else 'OFF'}")
            logger.info("Esperando cambio de estado del botón...")
            
            while True:
                boton_estado_actual = self.boton.is_pressed
                if boton_estado_actual != self.boton_estado_anterior:
                    logger.info(f"¡Botón cambiado de estado! Nuevo estado: {'ON' if not boton_estado_actual else 'OFF'}. Arrancando en 0.5s...")
                    time.sleep(0.5)
                    self.boton_estado_anterior = boton_estado_actual
                    return True
                time.sleep(0.05)
        else:
            logger.info("Botón no disponible. Presione ENTER...")
            input()
            return True

    def run(self):
        """Bucle principal de navegación."""
        if not self.esperar_inicio():
            return

        logger.info("=== INICIANDO NAVEGACIÓN ===")
        logger.info(f"Meta: {TOTAL_ESQUINAS} esquinas ({VUELTAS_OBJETIVO} vueltas)")
        
        self.servo_scanner.centrar()
        self.arduino.enviar(VELOCIDAD_RECTA, ANGULO_RECTO)
        
        primera_esquina = True
        
        try:
            while self.esquinas_completadas < TOTAL_ESQUINAS:
                ahora = time.monotonic()
                
                # Verificar cambio de estado del botón (parar/reiniciar carrera)
                if self.boton is not None:
                    boton_estado_actual = self.boton.is_pressed
                    if boton_estado_actual != self.boton_estado_anterior:
                        logger.info("[STOP] Botón cambiado de estado - Deteniendo carrera")
                        self.arduino.frenar()
                        logger.info("[REINICIO] Reiniciando carrera...")
                        time.sleep(1.0)
                        # Reiniciar estado
                        self.esquinas_completadas = 0
                        self.sentido_giro = None
                        self.angulo_giro = None
                        self.en_giro = False
                        self.tiempo_ultima_esquina = 0.0
                        self.en_esquiva = False
                        self.color_detectado = None
                        self.boton_estado_anterior = boton_estado_actual
                        primera_esquina = True
                        logger.info("[REINICIO] Carrera reiniciada. Continuando...")
                        self.servo_scanner.centrar()
                        self.arduino.enviar(VELOCIDAD_RECTA, ANGULO_RECTO)
                        continue
                    self.boton_estado_anterior = boton_estado_actual
                
                # Leer distancia frontal
                dist_frontal = self.ultrasonico_frontal.leer_distancia_cm()
                
                # Verificar retroceso seguro
                if self.retroceso_seguro():
                    continue
                
                # Detectar color
                color = self.vision.detectar_color()
                if color and color != self.color_detectado:
                    self.color_detectado = color
                    self.esquiva_pilar(color)
                    continue
                
                # Lógica de esquinas
                tiempo_desde_esquina = ahora - self.tiempo_ultima_esquina
                
                if not self.en_giro and not self.en_esquiva:
                    if dist_frontal > 0 and dist_frontal <= DISTANCIA_ESQUINA_CM and tiempo_desde_esquina >= COOLDOWN_ESQUINA_SEG:
                        logger.info(f"[ESQUINA] Muro detectado a {dist_frontal:.0f}cm")
                        
                        if primera_esquina:
                            # Autodetectar sentido en primera esquina
                            self.autodetectar_sentido_giro()
                            primera_esquina = False
                        
                        self.en_giro = True
                        self.tiempo_inicio_giro = ahora
                        
                        # Ejecutar giro
                        logger.info(f"[GIRO] Girando {self.sentido_giro} a {self.angulo_giro}°")
                        self.arduino.enviar(VELOCIDAD_GIRO, self.angulo_giro)
                
                # Finalizar giro
                if self.en_giro:
                    tiempo_en_giro = ahora - self.tiempo_inicio_giro
                    if tiempo_en_giro >= DURACION_GIRO_SEG:
                        self.en_giro = False
                        self.esquinas_completadas += 1
                        self.tiempo_ultima_esquina = ahora
                        logger.info(f"[ESQUINA] ✓ Completada ({self.esquinas_completadas}/{TOTAL_ESQUINAS})")
                        
                        # Volver a recta
                        self.arduino.enviar(VELOCIDAD_RECTA, ANGULO_RECTO)
                
                time.sleep(0.025)  # ~40Hz
            
            logger.info("=== CARRERA COMPLETADA ===")
            self.arduino.frenar()
            
        except KeyboardInterrupt:
            logger.info("Interrumpido por usuario")
        finally:
            self.limpiar()

    def limpiar(self):
        logger.info("Cerrando subsistemas...")
        self.arduino.cerrar()
        self.servo_scanner.cerrar()
        self.ultrasonico_frontal.cerrar()
        self.ultrasonico_trasero.cerrar()
        self.vision.cerrar()
        logger.info("Sistema finalizado")

if __name__ == "__main__":
    sistema = SafetyUltrasonico()
    sistema.run()
