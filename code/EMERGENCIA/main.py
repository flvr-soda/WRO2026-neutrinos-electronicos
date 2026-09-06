#!/usr/bin/env python3
"""
SISTEMA DE EMERGENCIA WRO - Modo Reactivo por LiDAR Frontal
Objetivo: Completar 3 vueltas (12 esquinas) al circuito en el menor tiempo posible.

Protocolo WRO:
1. Encendido: Inicializa sensores y queda en modo STANDBY.
2. Pulsador de retención: Al cambiar el estado del switch físico (GPIO 17), arranca la carrera.
3. Carrera: Avanza en línea recta y gira a la derecha al detectar pared frontal con LiDAR.
4. Finalización: Completa 12 esquinas (3 vueltas), frena y se detiene.

CONFIGURACIÓN: Todos los parámetros se cargan desde config.yaml en el mismo directorio.
"""

import time
import glob
import struct
import serial
import logging
import yaml
import os

try:
    from gpiozero import Button
except ImportError:
    Button = None

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

# Botón de inicio físico (Regla WRO 9.11)
# Compartido con el sistema principal - GPIO 17 (Pin físico 11)
PIN_BOTON_INICIO = config.get('hardware', {}).get('pin_boton_inicio', 17)

# Parámetros de navegación
VUELTAS_OBJETIVO = config.get('navegacion', {}).get('vueltas_objetivo', 3)
ESQUINAS_POR_VUELTA = config.get('navegacion', {}).get('esquinas_por_vuelta', 4)
TOTAL_ESQUINAS = VUELTAS_OBJETIVO * ESQUINAS_POR_VUELTA  # 12 esquinas en total

# Velocidades (-100 a 100)
VELOCIDAD_CRUCERO = config.get('velocidades', {}).get('crucero', 65)    # Velocidad en tramos rectos
VELOCIDAD_GIRO = config.get('velocidades', {}).get('giro', 45)       # Velocidad durante el viraje en esquina

# Ángulos del servo de dirección del carro (valores Arduino)
ANGULO_DIRECCION_RECTO = config.get('angulos_direccion', {}).get('recto', 90)
ANGULO_GIRO_DERECHA = config.get('angulos_direccion', {}).get('giro_derecha', 50)   # Ángulo para girar a la derecha

# Umbrales de distancia LiDAR (en cm)
DISTANCIA_GIRO_CM = config.get('lidar', {}).get('distancia_giro_cm', 75.0)      # Distancia a la pared frontal para iniciar el giro
DISTANCIA_DESPEJADA_CM = config.get('lidar', {}).get('distancia_despejada_cm', 110.0) # Distancia a la que se considera la pista despejada tras el giro

# Tiempos de control
DURACION_MAX_GIRO_SEG = config.get('tiempos', {}).get('duracion_max_giro_seg', 1.6)   # Tiempo máximo de giro forzado por esquina si la distancia tarda en despejarse
DURACION_MIN_GIRO_SEG = config.get('tiempos', {}).get('duracion_min_giro_seg', 0.5)   # Tiempo mínimo forzado con dirección a la derecha
TIEMPO_COOLDOWN_ESQUINA_SEG = config.get('tiempos', {}).get('cooldown_esquina_seg', 1.4) # Tiempo mínimo entre detección de esquinas para evitar rebotes/doble conteo
FRECUENCIA_CONTROL_HZ = config.get('navegacion', {}).get('frecuencia_control_hz', 40)    # Tasa del bucle principal

logging.basicConfig(
    level=logging.DEBUG,
    format='%(asctime)s [%(levelname)s] %(message)s'
)
logger = logging.getLogger("EMERGENCIA_LIDAR")

# DRIVER SERIAL TF-LUNA LIDAR DIRECTO
class DirectLidar:
    """Manejo serial directo y de baja latencia del sensor TF-Luna."""
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
        Lee el buffer serial y parsea la trama estándar de 9 bytes del TF-Luna.
        Cabecera: 0x59 0x59
        Retorna la distancia en cm o -1.0 si no hay lectura válida.
        """
        if not self.conn or not self.conn.is_open:
            return -1.0

        try:
            bytes_esperando = self.conn.in_waiting
            if bytes_esperando >= 9:
                data = self.conn.read(bytes_esperando)
                # Recorrer desde el final hacia el principio para obtener la lectura más reciente
                for i in range(len(data) - 8 - 1, -1, -1):
                    if data[i] == 0x59 and data[i+1] == 0x59:
                        frame = data[i:i+9]
                        if len(frame) == 9:
                            dist_cm = struct.unpack('<H', frame[2:4])[0]
                            calidad = frame[1]
                            # Calidad > 15 asegura señal real (0 = sin señal, no válido)
                            if dist_cm > 0 and calidad > 15:
                                return float(dist_cm)
        except Exception as e:
            logger.debug(f"Error al leer trama LiDAR: {e}")

        return -1.0

    def cerrar(self):
        if self.conn and self.conn.is_open:
            self.conn.close()

# DRIVER SERIAL ARDUINO DIRECTO
class DirectArduino:
    """Envío directo de consignas de velocidad y ángulo al Arduino."""
    def __init__(self, baudrate=BAUD_ARDUINO):
        self.baudrate = baudrate
        self.conn = None
        self.port = self._buscar_puerto()
        self.ultimo_warning_conexion = 0.0  # Para evitar warnings repetitivos
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

            # Limpiar buffer de recepción
            self.conn.reset_input_buffer()
            self.conn.reset_output_buffer()
        except Exception as e:
            logger.error(f"Error conectando a Arduino en {self.port}: {e}")
            self.conn = None

    def enviar(self, velocidad: int, angulo: int):
        """Envía comando en formato V:<vel>;A:<ang>\n"""
        if not self.conn or not self.conn.is_open:
            # Solo mostrar warning cada 5 segundos para no saturar
            ahora = time.monotonic()
            if ahora - self.ultimo_warning_conexion > 5.0:
                logger.warning("Arduino no conectado, no se puede enviar comando")
                self.ultimo_warning_conexion = ahora
            return

        # Clamp de seguridad
        velocidad = max(-100, min(100, int(velocidad)))
        angulo = max(10, min(170, int(angulo)))  # Aumentado rango para mayor giro

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


# PROGRAMA PRINCIPAL DE NAVEGACIÓN
class EmergencyLidarRunner:
    def __init__(self):
        logger.info("Inicializando componentes del Sistema de Emergencia...")
        self.lidar = DirectLidar(PUERTO_LIDAR, BAUD_LIDAR)
        self.arduino = DirectArduino(BAUD_ARDUINO)
        self.boton = None

        # Inicializar Botón de Inicio físico (GPIO 17)
        if Button is not None:
            try:
                self.boton = Button(PIN_BOTON_INICIO, pull_up=True)
                logger.info(f"Pulsador de retención configurado en GPIO {PIN_BOTON_INICIO} (Pin físico 11)")
            except Exception as e:
                logger.warning(f"No se pudo inicializar pulsador de retención en GPIO {PIN_BOTON_INICIO}: {e}")
                self.boton = None

        self.esquinas_completadas = 0
        self.en_giro = False
        self.tiempo_inicio_giro = 0.0
        # Inicializado en negativo para que el primer cooldown transcurra desde el arranque
        self.tiempo_ultima_esquina = 0.0
        self.ultima_distancia_valida = 300.0
        self.boton_estado_anterior = None  # Para detectar cambios del switch durante carrera
        self.ultima_distancia_log = 0.0  # Para evitar logs repetitivos

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

    def run(self):
        # Loop principal para permitir múltiples carreras con el mismo switch
        while True:
            # 1. Modo Standby tras encendido (no avanza hasta pulsar el botón de inicio)
            if not self.esperar_inicio():
                self.limpiar()
                return

            logger.info("=== INICIANDO NAVEGACIÓN DE EMERGENCIA ===")
            logger.info(f"Meta: {VUELTAS_OBJETIVO} vueltas ({TOTAL_ESQUINAS} esquinas).")
            logger.info(f"Umbral de giro frontal: {DISTANCIA_GIRO_CM} cm.")
            logger.info(f"Velocidad crucero: {VELOCIDAD_CRUCERO}, Ángulo recto: {ANGULO_DIRECCION_RECTO}")

            periodo_bucle = 1.0 / FRECUENCIA_CONTROL_HZ

            # Cooldown inicial: forzar espera del cooldown completo antes de detectar la primera esquina
            # Evita que una pared cercana al arranque dispare un giro falso inmediato
            self.tiempo_ultima_esquina = time.monotonic()
            
            # Centrar servo antes de iniciar carrera
            logger.info(f"[CENTRAR] Servo a {ANGULO_DIRECCION_RECTO}°")
            self.arduino.enviar(0, ANGULO_DIRECCION_RECTO)
            time.sleep(0.5)
            
            # Inicializar estado del switch para detección durante carrera
            if self.boton is not None:
                self.boton_estado_anterior = self.boton.is_pressed
            
            # Enviar comando inicial para arrancar motores
            logger.info(f"[ARRANQUE] Vel: {VELOCIDAD_CRUCERO}, Ang: {ANGULO_DIRECCION_RECTO}°")
            self.arduino.enviar(VELOCIDAD_CRUCERO, ANGULO_DIRECCION_RECTO)

            carrera_detenida = False
            try:
                counter = 0
                while self.esquinas_completadas < TOTAL_ESQUINAS:
                    t_inicio_iter = time.monotonic()
                    ahora = time.monotonic()
                    counter += 1

                    # Leer telemetría del Arduino para verificar comunicación
                    self.arduino.leer_telemetria()

                    # Verificar cambio del switch de inicio (parada de emergencia)
                    if self.boton is not None:
                        boton_estado_actual = self.boton.is_pressed
                        if boton_estado_actual != self.boton_estado_anterior:
                            logger.info("[STOP] Switch de inicio cambiado - Deteniendo carrera")
                            self.boton_estado_anterior = boton_estado_actual
                            carrera_detenida = True
                            break  # Salir del loop de carrera

                    # 1. Leer distancia frontal del LiDAR
                    distancia = self.lidar.leer_distancia_cm()
                    if distancia > 0:
                        self.ultima_distancia_valida = distancia

                    dist = self.ultima_distancia_valida

                    # 2. Máquina de estados reactiva
                    if not self.en_giro:
                        # Chequear si llegamos a la esquina frontal
                        tiempo_desde_ultimo_giro = ahora - self.tiempo_ultima_esquina
                        if dist <= DISTANCIA_GIRO_CM and tiempo_desde_ultimo_giro >= TIEMPO_COOLDOWN_ESQUINA_SEG:
                            # Iniciar maniobra de giro a la derecha
                            self.en_giro = True
                            self.tiempo_inicio_giro = ahora
                            self.tiempo_ultima_esquina = ahora
                            self.esquinas_completadas += 1
                            vueltas = (self.esquinas_completadas - 1) // ESQUINAS_POR_VUELTA
                            esq_en_vuelta = ((self.esquinas_completadas - 1) % ESQUINAS_POR_VUELTA) + 1
                            
                            logger.info(f"[ESQUINA #{self.esquinas_completadas}] V{vueltas+1}-E{esq_en_vuelta} a {dist:.0f}cm")
                            self.arduino.enviar(VELOCIDAD_GIRO, ANGULO_GIRO_DERECHA)
                        else:
                            # Recta normal - log solo cuando hay cambio significativo en distancia (>10cm)
                            cambio_distancia = abs(dist - self.ultima_distancia_log)
                            if cambio_distancia > 10.0:
                                logger.info(f"[RECTA] {dist:.0f}cm | V:{VELOCIDAD_CRUCERO} A:{ANGULO_DIRECCION_RECTO}")
                                self.ultima_distancia_log = dist
                            self.arduino.enviar(VELOCIDAD_CRUCERO, ANGULO_DIRECCION_RECTO)

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
                            logger.info(f"[FIN GIRO] {tiempo_en_giro:.1f}s | Recta")
                            self.arduino.enviar(VELOCIDAD_CRUCERO, ANGULO_DIRECCION_RECTO)
                        else:
                            # Mantener viraje a la derecha
                            self.arduino.enviar(VELOCIDAD_GIRO, ANGULO_GIRO_DERECHA)

                    # Control de frecuencia
                    t_transcurrido = time.monotonic() - t_inicio_iter
                    t_dormir = periodo_bucle - t_transcurrido
                    if t_dormir > 0:
                        time.sleep(t_dormir)

                logger.info(f"¡RETO COMPLETADO! Se completaron {TOTAL_ESQUINAS} esquinas ({VUELTAS_OBJETIVO} vueltas).")

            except KeyboardInterrupt:
                logger.info("Interrupción manual por teclado.")
                carrera_detenida = True
            except Exception as e:
                logger.error(f"Error inesperado en loop de emergencia: {e}", exc_info=True)
                carrera_detenida = True
            
            # Frenar motores después de la carrera (completada o detenida)
            if self.arduino:
                self.arduino.frenar()
                time.sleep(0.1)
            
            # Si la carrera fue detenida por el switch, reiniciar contador para nueva carrera
            if carrera_detenida:
                logger.info("[REINICIO] Carrera detenida por switch - Reiniciando para nueva carrera")
                self.esquinas_completadas = 0
                self.en_giro = False
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
        # No cerrar el botón GPIO si estamos en loop principal para múltiples carreras
        # Solo cerrarlo cuando realmente termine el programa
        logger.info("Sistema de emergencia finalizado con éxito.")


def main():
    runner = EmergencyLidarRunner()
    runner.run()


if __name__ == "__main__":
    main()


