
#!/usr/bin/env python3
"""
SISTEMA DE EMERGENCIA WRO - Reto de Obstáculos (LiDAR + Servo)
Objetivo: Completar 3 vueltas (12 esquinas) esquivando obstáculos en el trayecto.

Protocolo WRO:
1. Encendido: Inicializa sensores y queda en modo STANDBY.
2. Botón de inicio: Al presionar el botón físico (GPIO 23), arranca la carrera.
3. Carrera:
   - Avanza en recta. LiDAR apunta al frente (90°).
   - Si detecta obstáculo frontal cercano (<= DIST_OBSTACULO_CM):
       Hace mini barrido: mide a izquierda (~60°) y derecha (~120°).
       Esquiva por el lado con mayor espacio libre.
   - Si detecta pared de contención (<= DIST_PARED_ESQUINA_CM):
       Gira a la derecha y cuenta la esquina.
4. Finalización: Completa 12 esquinas (3 vueltas), frena y se detiene.

NOTA: Sin cámara, no se detecta color del pilar. El algoritmo esquiva
      por el lado con más espacio, lo cual puede no cumplir la regla de colores.
"""

import time
import glob
import struct
import serial
import logging

try:
    from gpiozero import Button, AngularServo
except ImportError:
    Button = None
    AngularServo = None

# CONFIGURACIÓN DIRECTA

# Conexiones seriales
PUERTO_LIDAR = "/dev/serial0"
BAUD_LIDAR = 115200
BAUD_ARDUINO = 115200

# Servo del LiDAR (para mini barrido de esquiva)
PIN_SERVO_LIDAR = 18
ANGULO_FRENTE = 90      # LiDAR mirando al frente
ANGULO_IZQUIERDA = 60   # LiDAR mirando a la izquierda
ANGULO_DERECHA = 120    # LiDAR mirando a la derecha

# Botón de inicio físico (Regla WRO 9.11)
PIN_BOTON_INICIO = 23   # GPIO 23 (Pin físico 16)

# Parámetros de navegación
VUELTAS_OBJETIVO = 3
ESQUINAS_POR_VUELTA = 4
TOTAL_ESQUINAS = VUELTAS_OBJETIVO * ESQUINAS_POR_VUELTA  # 12 esquinas

# Velocidades (-100 a 100)
VELOCIDAD_CRUCERO = 60    # Velocidad en tramos rectos
VELOCIDAD_ESQUIVA = 40    # Velocidad durante la maniobra de esquiva
VELOCIDAD_GIRO = 40       # Velocidad durante el giro de esquina

# Ángulos del servo de dirección del carro (valores Arduino)
ANGULO_DIRECCION_RECTO = 90
ANGULO_GIRO_DERECHA = 50    # Giro máximo derecha
ANGULO_GIRO_IZQUIERDA = 130 # Giro máximo izquierda

# Umbrales de distancia LiDAR (en cm)
DIST_PARED_ESQUINA_CM = 75.0   # Distancia frontal para iniciar giro de esquina
DIST_OBSTACULO_CM = 50.0       # Distancia frontal para detectar pilar obstáculo
                                # Debe ser < DIST_PARED_ESQUINA_CM
DIST_LIBRE_CM = 90.0           # Distancia a la que se considera la pista despejada

# Tiempos de control de esquina
DURACION_MAX_GIRO_ESQUINA_SEG = 1.6
DURACION_MIN_GIRO_ESQUINA_SEG = 0.5
TIEMPO_COOLDOWN_ESQUINA_SEG = 1.4

# Tiempos de control de esquiva de obstáculo
DURACION_ESQUIVA_SEG = 0.8      # Tiempo máximo con dirección de esquiva aplicada
DURACION_MIN_ESQUIVA_SEG = 0.3  # Tiempo mínimo de esquiva forzado

# Tiempo de asentamiento del servo LiDAR para barrido
MS_POR_GRADO_SERVO = 5         # ~5 ms/grado para barrido rápido

FRECUENCIA_CONTROL_HZ = 40     # Tasa del bucle principal

logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s [%(levelname)s] %(message)s'
)
logger = logging.getLogger("EMERGENCIA_OBSTACULOS")


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
                self.servo = AngularServo(PIN_SERVO_LIDAR, min_angle=-90, max_angle=90, initial_angle=0)
                self.apuntar(ANGULO_FRENTE)
                logger.info(f"Servo LiDAR inicializado en GPIO {PIN_SERVO_LIDAR}")
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
            return

        velocidad = max(-100, min(100, int(velocidad)))
        angulo = max(40, min(140, int(angulo)))

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

        if Button is not None:
            try:
                self.boton = Button(PIN_BOTON_INICIO, pull_up=True)
                logger.info(f"Botón de inicio configurado en GPIO {PIN_BOTON_INICIO} (Pin físico 16)")
            except Exception as e:
                logger.warning(f"No se pudo inicializar botón: {e}")
                self.boton = None

        self.estado = self.ESTADO_RECTA
        self.esquinas_completadas = 0
        self.tiempo_inicio_maniobra = 0.0
        self.tiempo_ultima_esquina = 0.0
        self.ultima_distancia_valida = 300.0
        self.angulo_esquiva_activo = ANGULO_DIRECCION_RECTO

    def esperar_inicio(self):
        """Modo STANDBY hasta que se presione el botón de inicio (Regla WRO 9.11)."""
        logger.info("==================================================")
        logger.info("[STANDBY] Robot encendido y listo en zona de salida.")

        if self.boton is not None:
            logger.info(f"Esperando pulsación del botón de inicio (GPIO {PIN_BOTON_INICIO})...")
            try:
                self.boton.wait_for_press()
                logger.info("¡Botón de inicio presionado! Arrancando en 0.5 segundos...")
                time.sleep(0.5)
                return True
            except KeyboardInterrupt:
                logger.info("Cancelado en standby por teclado.")
                return False
        else:
            logger.info("Botón GPIO no disponible. Presione ENTER en consola para iniciar carrera...")
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

        logger.info(f"[BARRIDO] Izq: {dist_izq:.1f} cm | Der: {dist_der:.1f} cm")

        if dist_izq >= dist_der:
            logger.info("[BARRIDO] → Más espacio a la IZQUIERDA")
            return ANGULO_GIRO_IZQUIERDA
        else:
            logger.info("[BARRIDO] → Más espacio a la DERECHA")
            return ANGULO_GIRO_DERECHA

    def run(self):
        # 1. Standby hasta botón de inicio
        if not self.esperar_inicio():
            self.limpiar()
            return

        logger.info("=== INICIANDO RETO DE OBSTÁCULOS ===")
        logger.info(f"Meta: {VUELTAS_OBJETIVO} vueltas ({TOTAL_ESQUINAS} esquinas).")

        periodo_bucle = 1.0 / FRECUENCIA_CONTROL_HZ

        # Cooldown inicial: evitar giro falso si arranca cerca de una pared
        self.tiempo_ultima_esquina = time.monotonic()

        try:
            while self.esquinas_completadas < TOTAL_ESQUINAS:
                t_inicio_iter = time.monotonic()
                ahora = time.monotonic()

                # 1. Leer distancia frontal del LiDAR
                distancia = self.lidar.leer_distancia_cm()
                if distancia > 0:
                    self.ultima_distancia_valida = distancia

                dist = self.ultima_distancia_valida

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
                        logger.info(
                            f"[ESQUINA] #{self.esquinas_completadas}/{TOTAL_ESQUINAS} "
                            f"(Vuelta {vueltas + 1}, Esquina {esq_en_vuelta}) | dist: {dist:.1f} cm"
                        )
                        self.arduino.enviar(VELOCIDAD_GIRO, ANGULO_GIRO_DERECHA)

                    # Prioridad 2: Obstáculo (pilar) → barrido y esquiva
                    elif dist <= DIST_OBSTACULO_CM and tiempo_desde_esquina >= TIEMPO_COOLDOWN_ESQUINA_SEG:
                        logger.info(f"[OBSTÁCULO] Detectado a {dist:.1f} cm — haciendo barrido...")
                        angulo_esquiva = self.hacer_barrido_esquiva()
                        self.angulo_esquiva_activo = angulo_esquiva
                        self.estado = self.ESTADO_ESQUIVANDO
                        self.tiempo_inicio_maniobra = ahora
                        self.arduino.enviar(VELOCIDAD_ESQUIVA, angulo_esquiva)

                    # Prioridad 3: Recta libre
                    else:
                        self.arduino.enviar(VELOCIDAD_CRUCERO, ANGULO_DIRECCION_RECTO)

                elif self.estado == self.ESTADO_ESQUIVANDO:
                    tiempo_esquivando = ahora - self.tiempo_inicio_maniobra

                    esquiva_completa = False
                    if tiempo_esquivando >= DURACION_MIN_ESQUIVA_SEG:
                        if dist >= DIST_LIBRE_CM or tiempo_esquivando >= DURACION_ESQUIVA_SEG:
                            esquiva_completa = True

                    if esquiva_completa:
                        self.estado = self.ESTADO_RECTA
                        logger.info(f"[FIN ESQUIVA] Despejado ({dist:.1f} cm) en {tiempo_esquivando:.2f}s.")
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
                        logger.info(f"[FIN ESQUINA] Despejado ({dist:.1f} cm) en {tiempo_girando:.2f}s.")
                        self.arduino.enviar(VELOCIDAD_CRUCERO, ANGULO_DIRECCION_RECTO)
                    else:
                        self.arduino.enviar(VELOCIDAD_GIRO, ANGULO_GIRO_DERECHA)

                # Control de frecuencia del bucle
                t_transcurrido = time.monotonic() - t_inicio_iter
                t_dormir = periodo_bucle - t_transcurrido
                if t_dormir > 0:
                    time.sleep(t_dormir)

            logger.info(f"¡RETO COMPLETADO! Se completaron {TOTAL_ESQUINAS} esquinas ({VUELTAS_OBJETIVO} vueltas).")

        except KeyboardInterrupt:
            logger.info("Interrupción manual por teclado.")
        except Exception as e:
            logger.error(f"Error inesperado en loop de obstáculos: {e}", exc_info=True)
        finally:
            self.limpiar()

    def limpiar(self):
        logger.info("Deteniendo robot y cerrando conexiones...")
        if self.arduino:
            self.arduino.frenar()
            time.sleep(0.1)
            self.arduino.cerrar()
        if self.lidar:
            self.lidar.cerrar()
        if self.boton:
            try:
                self.boton.close()
            except Exception:
                pass
        logger.info("Sistema de obstáculos finalizado con éxito.")


def main():
    runner = ObstacleRunner()
    runner.run()


if __name__ == "__main__":
    main()
