#!/usr/bin/env python3
"""
SISTEMA DE EMERGENCIA WRO - Modo Reactivo por LiDAR Frontal
Objetivo: Completar 3 vueltas (12 esquinas) al circuito en el menor tiempo posible.

Protocolo WRO:
1. Encendido: Inicializa sensores y queda en modo STANDBY.
2. Botón de inicio: Al presionar el botón físico (GPIO 23), arranca la carrera.
3. Carrera: Avanza en línea recta y gira a la derecha al detectar pared frontal con LiDAR.
4. Finalización: Completa 12 esquinas (3 vueltas), frena y se detiene.
"""

import time
import glob
import struct
import serial
import logging

try:
    from gpiozero import Button
except ImportError:
    Button = None

# CONFIGURACIÓN DIRECTA

# Conexiones seriales
PUERTO_LIDAR = "/dev/serial0"
BAUD_LIDAR = 115200
BAUD_ARDUINO = 115200

# Botón de inicio físico (Regla WRO 9.11)
# Compartido con el sistema principal - GPIO 23 (Pin físico 16)
PIN_BOTON_INICIO = 23

# Parámetros de navegación
VUELTAS_OBJETIVO = 3
ESQUINAS_POR_VUELTA = 4
TOTAL_ESQUINAS = VUELTAS_OBJETIVO * ESQUINAS_POR_VUELTA  # 12 esquinas en total

# Velocidades (-100 a 100)
VELOCIDAD_CRUCERO = 65    # Velocidad en tramos rectos
VELOCIDAD_GIRO = 45       # Velocidad durante el viraje en esquina

# Ángulos del servo de dirección del carro (valores Arduino)
ANGULO_DIRECCION_RECTO = 90
ANGULO_GIRO_DERECHA = 50   # Ángulo para girar a la derecha

# Umbrales de distancia LiDAR (en cm)
DISTANCIA_GIRO_CM = 75.0      # Distancia a la pared frontal para iniciar el giro
DISTANCIA_DESPEJADA_CM = 110.0 # Distancia a la que se considera la pista despejada tras el giro

# Tiempos de control
DURACION_MAX_GIRO_SEG = 1.6   # Tiempo máximo de giro forzado por esquina si la distancia tarda en despejarse
DURACION_MIN_GIRO_SEG = 0.5   # Tiempo mínimo forzado con dirección a la derecha
TIEMPO_COOLDOWN_ESQUINA_SEG = 1.4 # Tiempo mínimo entre detección de esquinas para evitar rebotes/doble conteo
FRECUENCIA_CONTROL_HZ = 40    # Tasa del bucle principal

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
            logger.warning("Arduino no conectado, no se puede enviar comando")
            return

        # Clamp de seguridad
        velocidad = max(-100, min(100, int(velocidad)))
        angulo = max(40, min(140, int(angulo)))

        comando = f"V:{velocidad};A:{angulo}\n"
        try:
            self.conn.write(comando.encode('utf-8'))
            self.conn.flush()
            logger.debug(f"Enviado a Arduino: {comando.strip()}")
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
                    logger.debug(f"Telemetría Arduino: {linea}")
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

        # Inicializar Botón de Inicio físico (GPIO 23)
        if Button is not None:
            try:
                self.boton = Button(PIN_BOTON_INICIO, pull_up=True)
                logger.info(f"Botón de inicio configurado en GPIO {PIN_BOTON_INICIO} (Pin físico 16)")
            except Exception as e:
                logger.warning(f"No se pudo inicializar botón en GPIO {PIN_BOTON_INICIO}: {e}")
                self.boton = None

        self.esquinas_completadas = 0
        self.en_giro = False
        self.tiempo_inicio_giro = 0.0
        # Inicializado en negativo para que el primer cooldown transcurra desde el arranque
        self.tiempo_ultima_esquina = 0.0
        self.ultima_distancia_valida = 300.0

    def esperar_inicio(self):
        """
        Modo STANDBY tras encendido.
        Espera a que se active el switch de inicio físico (Regla WRO 9.11).
        Detecta el flanco de subida (switch de off a on).
        """
        logger.info("==================================================")
        logger.info("[STANDBY] Robot encendido y listo en zona de salida.")

        if self.boton is not None:
            logger.info(f"Esperando activación del switch de inicio (GPIO {PIN_BOTON_INICIO})...")
            logger.info(f"Estado inicial del switch: {'ACTIVO' if self.boton.is_pressed else 'INACTIVO'}")
            try:
                # Esperar a que el switch se active (flanco de subida)
                switch_state = False
                counter = 0
                while True:
                    current_state = self.boton.is_pressed
                    # Log cada 20 iteraciones para no saturar
                    counter += 1
                    if counter % 20 == 0:
                        logger.debug(f"Estado actual del switch: {'ACTIVO' if current_state else 'INACTIVO'}")
                    # Detectar flanco de subida: estaba apagado y ahora está encendido
                    if current_state and not switch_state:
                        logger.info("¡Switch de inicio activado! Arrancando en 0.5 segundos...")
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
        # 1. Modo Standby tras encendido (no avanza hasta pulsar el botón de inicio)
        if not self.esperar_inicio():
            self.limpiar()
            return

        logger.info("=== INICIANDO NAVEGACIÓN DE EMERGENCIA ===")
        logger.info(f"Meta: {VUELTAS_OBJETIVO} vueltas ({TOTAL_ESQUINAS} esquinas).")
        logger.info(f"Umbral de giro frontal: {DISTANCIA_GIRO_CM} cm.")

        periodo_bucle = 1.0 / FRECUENCIA_CONTROL_HZ

        # Cooldown inicial: forzar espera del cooldown completo antes de detectar la primera esquina
        # Evita que una pared cercana al arranque dispare un giro falso inmediato
        self.tiempo_ultima_esquina = time.monotonic()

        try:
            while self.esquinas_completadas < TOTAL_ESQUINAS:
                t_inicio_iter = time.monotonic()
                ahora = time.monotonic()  # Usar reloj monotónico en todo el bucle (inmune a NTP)

                # Leer telemetría del Arduino para verificar comunicación
                self.arduino.leer_telemetria()

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
                        
                        logger.info(
                            f"[ESQUINA DETECTADA] #{self.esquinas_completadas}/{TOTAL_ESQUINAS} "
                            f"(Vuelta {vueltas + 1}, Esquina {esq_en_vuelta}) - Distancia: {dist:.1f} cm"
                        )
                        self.arduino.enviar(VELOCIDAD_GIRO, ANGULO_GIRO_DERECHA)
                    else:
                        # Recta normal
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
                        logger.info(f"[FIN GIRO] Pista despejada ({dist:.1f} cm) en {tiempo_en_giro:.2f}s. Recta.")
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
        if self.lidar:
            self.lidar.cerrar()
        if self.boton:
            try:
                self.boton.close()
            except Exception:
                pass
        logger.info("Sistema de emergencia finalizado con éxito.")


def main():
    runner = EmergencyLidarRunner()
    runner.run()


if __name__ == "__main__":
    main()


