#!/usr/bin/env python3
"""
SISTEMA DE ALTERNATIVO WRO - Modo Reactivo por Ultrasónico Frontal
Objetivo: Completar 3 vueltas (12 esquinas) al circuito en el menor tiempo posible.

Protocolo WRO:
1. Encendido: Inicializa sensores y queda en modo STANDBY.
2. Pulsador de retención: Al cambiar el estado del switch físico (GPIO 17), arranca la carrera.
3. Carrera: Avanza en línea recta y gira a la derecha al detectar pared frontal con ultrasónico.
4. Finalización: Completa 12 esquinas (3 vueltas), frena y se detiene.

CONFIGURACIÓN: Valores configurados directamente en código.
"""

import time
import glob
import serial
import logging
import os

# Configurar pin factory RPi.GPIO (necesario para PWM en servo)
os.environ['GPIOZERO_PIN_FACTORY'] = 'rpigpio'

try:
    from gpiozero import DigitalOutputDevice, InputDevice, AngularServo
    import RPi.GPIO as GPIO
    # Configurar modo BCM una sola vez al inicio
    GPIO.setmode(GPIO.BCM)
    GPIO.setwarnings(False)
except ImportError:
    DigitalOutputDevice = None
    InputDevice = None
    AngularServo = None
    GPIO = None

# CONFIGURACIÓN DIRECTA

# Conexiones seriales
BAUD_ARDUINO = 115200

# Botón de inicio físico (Regla WRO 9.11)
# Compartido con el sistema principal - GPIO 17 (Pin físico 11)
PIN_BOTON_INICIO = 17

# Parámetros de navegación
VUELTAS_OBJETIVO = 3
ESQUINAS_POR_VUELTA = 4
TOTAL_ESQUINAS = VUELTAS_OBJETIVO * ESQUINAS_POR_VUELTA  # 12 esquinas en total

# Velocidades (-100 a 100)
VELOCIDAD_CRUCERO = 65    # Velocidad en tramos rectos
VELOCIDAD_GIRO = 45       # Velocidad durante el viraje en esquina

# Ángulos del servo de dirección del carro (valores Arduino - rango completo SG90)
# Nota: Estos valores son referenciales, el firmware usa comandos simples (C/D/I)
ANGULO_DIRECCION_RECTO = 90
ANGULO_GIRO_DERECHA = 0   # Extrema derecha (0°)
ANGULO_GIRO_IZQUIERDA = 180 # Extrema izquierda (180°)

# Umbrales de distancia ultrasónico (en cm)
DISTANCIA_GIRO_CM = 75.0      # Distancia a la pared frontal para iniciar el giro
DISTANCIA_DESPEJADA_CM = 110.0 # Distancia a la que se considera la pista despejada tras el giro
DISTANCIA_LIBRE_CM = 100.0    # Distancia mínima para considerar una dirección libre

# Tiempos de control
DURACION_MAX_GIRO_SEG = 1.6   # Tiempo máximo de giro forzado por esquina si la distancia tarda en despejarse
DURACION_MIN_GIRO_SEG = 0.5   # Tiempo mínimo forzado con dirección a la derecha
TIEMPO_COOLDOWN_ESQUINA_SEG = 1.4 # Tiempo mínimo entre detección de esquinas para evitar rebotes/doble conteo
FRECUENCIA_CONTROL_HZ = 40    # Tasa del bucle principal

logging.basicConfig(
    level=logging.DEBUG,
    format='%(asctime)s [%(levelname)s] %(message)s'
)
logger = logging.getLogger("EMERGENCIA_ULTRASONICO")

# DRIVER BOTÓN MANUAL (polling sin edge detection)
class ManualButton:
    """Botón con polling manual para evitar problemas de edge detection."""
    def __init__(self, pin, pull_up=True):
        self.pin = pin
        self.pull_up = pull_up
        self._inicializar()

    def _inicializar(self):
        if GPIO is None:
            logger.warning("RPi.GPIO no disponible para botón manual")
            return
        try:
            if self.pull_up:
                GPIO.setup(self.pin, GPIO.IN, pull_up_down=GPIO.PUD_UP)
            else:
                GPIO.setup(self.pin, GPIO.IN)
            logger.info(f"Botón manual inicializado en GPIO {self.pin}")
        except Exception as e:
            logger.warning(f"Error inicializando botón manual: {e}")

    @property
    def is_pressed(self):
        if GPIO is None:
            return False
        try:
            return GPIO.input(self.pin) == GPIO.LOW if self.pull_up else GPIO.input(self.pin) == GPIO.HIGH
        except Exception:
            return False

    def close(self):
        if GPIO is not None:
            try:
                GPIO.cleanup(self.pin)
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
            logger.warning("[CONECT] No se encontró puerto Arduino automáticamente.")
            return

        try:
            logger.info(f"[CONECT] Intentando conectar a Arduino en {self.port} a {self.baudrate} baud...")
            self.conn = serial.Serial(self.port, self.baudrate, timeout=0.1)
            time.sleep(1.8)  # Tiempo de reinicio del bootloader de Arduino
            logger.info(f"[CONECT] Arduino conectado exitosamente en {self.port}")
            logger.info(f"[CONECT] Estado conexión: {self.conn.is_open}")

            # Limpiar buffer de recepción
            self.conn.reset_input_buffer()
            self.conn.reset_output_buffer()
            logger.info(f"[CONECT] Buffers limpiados")
        except Exception as e:
            logger.error(f"[ERROR] Error conectando a Arduino en {self.port}: {e}")
            self.conn = None

    def enviar(self, velocidad: int, angulo: int):
        """Envía comando en formato V:<vel>;A:<ang>\n"""
        if not self.conn or not self.conn.is_open:
            logger.warning("Arduino no conectado, no se puede enviar comando")
            return

        # Clamp de seguridad
        velocidad = max(-100, min(100, int(velocidad)))
        angulo = max(40, min(140, int(angulo)))

        comando = f"V:{velocidad};A:{angulo}\n"
        try:
            logger.info(f"[COMANDO] Raw: {repr(comando)} | Vel: {velocidad} | Ang: {angulo}")
            self.conn.write(comando.encode('utf-8'))
            self.conn.flush()
            logger.debug(f"[TX] Enviado a Arduino: {comando.strip()}")
        except Exception as e:
            logger.error(f"[ERROR] Error enviando comando a Arduino: {e}")

    def enviar_direccion(self, direccion: str):
        """Envía comando simple de dirección: C (centrar), D (derecha), I (izquierda)"""
        if not self.conn or not self.conn.is_open:
            logger.warning("Arduino no conectado, no se puede enviar comando de dirección")
            return

        if direccion not in ['C', 'D', 'I']:
            logger.warning(f"Dirección inválida: {direccion}. Debe ser C, D o I")
            return

        comando = f"{direccion}\n"
        try:
            logger.info(f"[COMANDO] Dirección: {direccion}")
            self.conn.write(comando.encode('utf-8'))
            self.conn.flush()
            logger.debug(f"[TX] Enviado a Arduino: {comando.strip()}")
        except Exception as e:
            logger.error(f"[ERROR] Error enviando comando de dirección: {e}")

    def enviar_servo_ultrasonico(self, posicion: str):
        """Envía comando para servo de ultrasónico: S (centro), L (izquierda), R (derecha)"""
        if not self.conn or not self.conn.is_open:
            logger.warning("Arduino no conectado, no se puede enviar comando de servo ultrasónico")
            return

        if posicion not in ['S', 'L', 'R']:
            logger.warning(f"Posición inválida: {posicion}. Debe ser S, L o R")
            return

        comando = f"{posicion}\n"
        try:
            logger.info(f"[COMANDO] Servo ultrasónico: {posicion}")
            self.conn.write(comando.encode('utf-8'))
            self.conn.flush()
            logger.debug(f"[TX] Enviado a Arduino: {comando.strip()}")
        except Exception as e:
            logger.error(f"[ERROR] Error enviando comando de servo ultrasónico: {e}")

    def enviar_velocidad(self, velocidad: int):
        """Envía comando simple de velocidad usando formato V:vel;A:90 (manteniendo dirección actual)"""
        if not self.conn or not self.conn.is_open:
            logger.warning("Arduino no conectado, no se puede enviar comando de velocidad")
            return

        # Clamp de seguridad
        velocidad = max(-100, min(100, int(velocidad)))

        comando = f"V:{velocidad};A:90\n"
        try:
            logger.info(f"[COMANDO] Velocidad: {velocidad}")
            self.conn.write(comando.encode('utf-8'))
            self.conn.flush()
            logger.debug(f"[TX] Enviado a Arduino: {comando.strip()}")
        except Exception as e:
            logger.error(f"[ERROR] Error enviando comando de velocidad: {e}")

    def leer_telemetria(self):
        """Lee telemetría del Arduino en formato D:distancia;"""
        if not self.conn or not self.conn.is_open:
            logger.warning("[RX] Arduino no conectado para telemetría")
            return None

        try:
            if self.conn.in_waiting > 0:
                linea = self.conn.readline().decode('utf-8', errors='ignore').strip()
                if linea:
                    # Parsear formato D:distancia;
                    if linea.startswith("D:"):
                        try:
                            distancia_str = linea[2:].replace(";", "")
                            distancia = float(distancia_str)
                            logger.info(f"[RX] Distancia frontal: {distancia:.1f} cm")
                            return distancia
                        except ValueError:
                            logger.warning(f"[RX] Formato de distancia inválido: {linea}")
                    else:
                        logger.info(f"[RX] Telemetría Arduino: {linea}")
        except Exception as e:
            logger.error(f"[ERROR] Error leyendo telemetría: {e}")
        return None

    def frenar(self):
        self.enviar_velocidad(0)
        self.enviar_direccion('C')

    def cerrar(self):
        if self.conn and self.conn.is_open:
            self.frenar()
            self.conn.close()


# PROGRAMA PRINCIPAL DE NAVEGACIÓN
class EmergencyUltrasonicRunner:
    def __init__(self):
        logger.info("Inicializando componentes del Sistema de Emergencia...")
        self.arduino = DirectArduino(BAUD_ARDUINO)
        self.boton = None

        # Inicializar Botón de Inicio físico (GPIO 17) usando polling manual
        if GPIO is not None:
            try:
                self.boton = ManualButton(PIN_BOTON_INICIO, pull_up=True)
                logger.info(f"Pulsador de retención configurado en GPIO {PIN_BOTON_INICIO} (Pin físico 11)")
            except Exception as e:
                logger.warning(f"No se pudo inicializar pulsador de retención en GPIO {PIN_BOTON_INICIO}: {e}")
                logger.warning("El sistema funcionará sin botón físico (requiere ENTER para iniciar)")
                self.boton = None

        self.esquinas_completadas = 0
        self.en_giro = False
        self.tiempo_inicio_giro = 0.0
        # Inicializado en negativo para que el primer cooldown transcurra desde el arranque
        self.tiempo_ultima_esquina = 0.0
        self.ultima_distancia_valida = 300.0
        self.boton_estado_anterior = False  # Para detección de cambios durante carrera
        self.sentido_giro = None  # 'derecha' o 'izquierda' detectado en primera esquina
        self.primera_esquina = True  # Flag para autodetectar sentido en primera esquina

    def autodetectar_sentido_giro(self):
        """
        Simplificado: siempre gira a la izquierda
        """
        return 'izquierda'

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
                        self.boton_estado_anterior = current_state
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

    def run(self):
        # 1. Modo Standby tras encendido (no avanza hasta pulsar el botón de inicio)
        if not self.esperar_inicio():
            self.limpiar()
            return

        logger.info("=== INICIANDO NAVEGACIÓN DE EMERGENCIA ===")
        logger.info(f"Meta: {VUELTAS_OBJETIVO} vueltas ({TOTAL_ESQUINAS} esquinas).")
        logger.info(f"Umbral de giro frontal: {DISTANCIA_GIRO_CM} cm.")
        logger.info(f"Velocidad crucero: {VELOCIDAD_CRUCERO}, Ángulo recto: {ANGULO_DIRECCION_RECTO}")
        logger.info(f"Sensor: Ultrasónico HC-SR04 (TRIGGER={PIN_ULTRASONICO_TRIGGER}, ECHO={PIN_ULTRASONICO_ECHO})")

        periodo_bucle = 1.0 / FRECUENCIA_CONTROL_HZ

        # Cooldown inicial: forzar espera del cooldown completo antes de detectar la primera esquina
        # Evita que una pared cercana al arranque dispare un giro falso inmediato
        self.tiempo_ultima_esquina = time.monotonic()
        
        # Enviar comando inicial para arrancar motores
        logger.info("Enviando comando inicial de arranque...")
        self.arduino.enviar_velocidad(VELOCIDAD_CRUCERO)
        self.arduino.enviar_direccion('C')

        try:
            counter = 0
            while self.esquinas_completadas < TOTAL_ESQUINAS:
                t_inicio_iter = time.monotonic()
                ahora = time.monotonic()  # Usar reloj monotónico en todo el bucle (inmune a NTP)
                counter += 1

                # Verificar cambio de estado del botón (toggle switch)
                if self.boton is not None:
                    boton_estado_actual = self.boton.is_pressed
                    
                    # Detectar cualquier cambio de estado (toggle)
                    if boton_estado_actual != self.boton_estado_anterior:
                        logger.info("[STOP] Switch cambiado de estado - Deteniendo carrera")
                        self.arduino.frenar()
                        
                        # Esperar otro cambio de estado para reiniciar
                        logger.info("[ESPERA] Esperando otro cambio de estado para reiniciar...")
                        while self.boton.is_pressed == boton_estado_actual:
                            time.sleep(0.1)
                        
                        logger.info("[REINICIO] Switch cambiado nuevamente - Reiniciando carrera...")
                        time.sleep(0.5)
                        
                        # Reiniciar estado
                        self.esquinas_completadas = 0
                        self.en_giro = False
                        self.tiempo_inicio_giro = 0.0
                        self.tiempo_ultima_esquina = time.monotonic()
                        self.ultima_distancia_valida = 300.0
                        self.boton_estado_anterior = self.boton.is_pressed
                        self.sentido_giro = None
                        self.primera_esquina = True
                        
                        logger.info("[REINICIO] Carrera reiniciada. Continuando...")
                        self.arduino.enviar_velocidad(VELOCIDAD_CRUCERO)
                        self.arduino.enviar_direccion('C')
                        continue

                # Leer telemetría del Arduino para obtener distancia frontal
                distancia = self.arduino.leer_telemetria()
                if distancia is not None and distancia > 0:
                    self.ultima_distancia_valida = distancia

                dist = self.ultima_distancia_valida

                # 2. Máquina de estados reactiva
                if not self.en_giro:
                    # Chequear si llegamos a la esquina frontal
                    tiempo_desde_ultimo_giro = ahora - self.tiempo_ultima_esquina
                    if dist <= DISTANCIA_GIRO_CM and tiempo_desde_ultimo_giro >= TIEMPO_COOLDOWN_ESQUINA_SEG:
                        # Iniciar maniobra de giro
                        self.en_giro = True
                        self.tiempo_inicio_giro = ahora
                        self.tiempo_ultima_esquina = ahora
                        self.esquinas_completadas += 1
                        vueltas = (self.esquinas_completadas - 1) // ESQUINAS_POR_VUELTA
                        esq_en_vuelta = ((self.esquinas_completadas - 1) % ESQUINAS_POR_VUELTA) + 1
                        
                        logger.info(
                            f"[ESQUINA DETECTADA] #{self.esquinas_completadas}/{TOTAL_ESQUINAS} "
                            f"(Vuelta {vueltas + 1}, Esquina {esq_en_vuelta}) - Distancia: {dist:.1f} cm"
                        )
                        
                        # Autodetectar sentido de giro en primera esquina
                        if self.primera_esquina:
                            self.arduino.frenar()
                            sentido = self.autodetectar_sentido_giro()
                            self.primera_esquina = False
                            logger.info(f"[PRIMERA ESQUINA] Sentido de giro detectado: {sentido}")
                        
                        # Determinar ángulo de giro según sentido detectado
                        if self.sentido_giro == 'izquierda':
                            direccion_giro = 'I'
                        else:
                            direccion_giro = 'D'
                        
                        logger.info(f"[GIRO] Girando a la {self.sentido_giro}")
                        self.arduino.enviar_velocidad(VELOCIDAD_GIRO)
                        self.arduino.enviar_direccion(direccion_giro)
                    else:
                        # Recta normal
                        if counter % 20 == 0:  # Log cada 20 iteraciones
                            logger.info(f"[RECTA] Distancia: {dist:.1f} cm, Velocidad: {VELOCIDAD_CRUCERO}")
                        self.arduino.enviar_velocidad(VELOCIDAD_CRUCERO)
                        self.arduino.enviar_direccion('C')

                else:
                    # En proceso de giro
                    tiempo_en_giro = ahora - self.tiempo_inicio_giro

                    # Salir del giro si ya cumplió el tiempo mínimo Y el frente se despejó, o si superó tiempo máximo
                    giro_completado = False
                    if tiempo_en_giro >= DURACION_MIN_GIRO_SEG:
                        if dist >= DISTANCIA_DESPEJADA_CM or tiempo_en_giro >= DURACION_MAX_GIRO_SEG:
                            giro_completado = True

                    if giro_completado:
                        self.en_giro = False
                        logger.info(f"[FIN GIRO] Pista despejada ({dist:.1f} cm) en {tiempo_en_giro:.2f}s. Recta.")
                        self.arduino.enviar_velocidad(VELOCIDAD_CRUCERO)
                        self.arduino.enviar_direccion('C')
                    else:
                        # Mantener viraje con la dirección actual
                        self.arduino.enviar_velocidad(VELOCIDAD_GIRO)
                        if self.sentido_giro == 'izquierda':
                            self.arduino.enviar_direccion('I')
                        else:
                            self.arduino.enviar_direccion('D')

                # Control de frecuencia
                t_transcurrido = time.monotonic() - t_inicio_iter
                t_dormir = periodo_bucle - t_transcurrido
                if t_dormir > 0:
                    time.sleep(t_dormir)

            logger.info(f"¡RETO COMPLETADO! Se completaron {TOTAL_ESQUINAS} esquinas ({VUELTAS_OBJETIVO} vueltas).")
            self.arduino.frenar()
            
            # Esperar cambio de estado del switch para reiniciar
            logger.info("==================================================")
            logger.info("[COMPLETADO] Cambie el estado del switch para reiniciar...")
            if self.boton is not None:
                switch_state = self.boton.is_pressed
                counter = 0
                while True:
                    current_state = self.boton.is_pressed
                    counter += 1
                    if counter % 20 == 0:
                        logger.debug(f"Estado actual del switch: {'ON' if not current_state else 'OFF'}")
                    if current_state != switch_state:
                        logger.info(f"¡Switch cambiado de estado! Nuevo estado: {'ON' if not current_state else 'OFF'}. Reiniciando en 1s...")
                        time.sleep(1.0)
                        
                        # Reiniciar estado
                        self.esquinas_completadas = 0
                        self.en_giro = False
                        self.tiempo_inicio_giro = 0.0
                        self.tiempo_ultima_esquina = time.monotonic()
                        self.ultima_distancia_valida = 300.0
                        self.boton_estado_anterior = current_state
                        
                        # Reiniciar carrera
                        logger.info("=== REINICIANDO NAVEGACIÓN ===")
                        self.arduino.enviar_velocidad(VELOCIDAD_CRUCERO)
                        self.arduino.enviar_direccion('C')
                        self.run()  # Llamada recursiva para reiniciar
                        return
                    switch_state = current_state
                    time.sleep(0.05)

        except KeyboardInterrupt:
            logger.info("Interrupción manual por teclado.")
        except Exception as e:
            logger.error(f"Error inesperado en loop de emergencia: {e}", exc_info=True)
        finally:
            self.limpiar()

    def limpiar(self):
        logger.info("Deteniendo robot y cerrando conexiones...")
        if self.arduino:
            self.arduino.frenar()
            time.sleep(0.1)
            self.arduino.cerrar()
        if self.boton:
            try:
                self.boton.close()
            except Exception:
                pass
        logger.info("Sistema de emergencia finalizado con éxito.")


def main():
    runner = EmergencyUltrasonicRunner()
    runner.run()


if __name__ == "__main__":
    main()


