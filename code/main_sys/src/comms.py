"""
Communication Modules - Arduino and LiDAR Serial Communication
"""

import re
import time
import logging
import threading
import queue
import serial
import glob
import struct
import os
from gpiozero import AngularServo, GPIOZeroError


# ==================== ARDUINO COMMUNICATION ====================

TELEMETRIA_REGEX = re.compile(r"T:Z:(-?\d+(?:\.\d+)?);A:(\d+);U:(-?\d+(?:\.\d+)?);")


class ArduinoComms:
    def __init__(self, baudrate=115200):
        """
        Inicializa comunicación con Arduino usando el primer puerto serial disponible.
        
        Args:
            baudrate: Velocidad de comunicación (default: 115200)
        """
        self.baudrate = baudrate
        self.serial_conn = None
        self.reconectando = False
        self.corriendo = True
        
        # Detectar primer puerto disponible
        self.port = self._get_first_available_port()
        if not self.port:
            logging.error("No se encontraron puertos seriales disponibles")
            raise RuntimeError("No se encontraron puertos seriales disponibles")
        
        self.telemetria_lock = threading.Lock()
        self.latest_telemetria = {
            "z": 0,
            "angulo": 90,
            "dist_trasera": -1.0
        }
        
        # Cola de Comandos para Envío Asíncrono
        self.cola_comandos = queue.Queue(maxsize=50)
        
        self.conectar()
        
        # Iniciar Hilo de Lectura de Telemetría
        self.hilo_telemetria = threading.Thread(target=self._worker_telemetria, daemon=True)
        self.hilo_telemetria.start()
        
        # Iniciar Hilo de Envío de Comandos
        self.hilo_envio = threading.Thread(target=self._worker_envio, daemon=True)
        self.hilo_envio.start()

    def conectar(self):
        try:
            self.serial_conn = serial.Serial(self.port, self.baudrate, timeout=1)
            time.sleep(2)  # Esperar reinicio del Arduino
            logging.info(f"Conectado a Arduino en {self.port} a {self.baudrate} baudios.")
        except serial.SerialException as e:
            logging.error(f"No se pudo conectar al puerto serial {self.port}: {e}")
            self.serial_conn = None

    @staticmethod
    def _get_first_available_port():
        """
        Busca el primer puerto serial disponible en el sistema.
        
        Retorna: Nombre del puerto o None si no se encuentra.
        """
        # Patrones de puertos seriales comunes en Linux
        port_patterns = ['/dev/ttyUSB*', '/dev/ttyACM*']
        
        for pattern in port_patterns:
            ports = glob.glob(pattern)
            if ports:
                # Retornar el primer puerto encontrado
                return ports[0]
        
        # Fallback para Raspberry Pi: intentar /dev/serial0 (UART via GPIO)
        if os.path.exists('/dev/serial0'):
            return '/dev/serial0'
        
        return None

    def _intento_reconexion(self):
        self.reconectando = True
        time.sleep(2)  # Pequeño backoff
        self.conectar()
        self.reconectando = False

    def enviar_comando(self, velocidad: int, angulo: int):
        """Envía comando a través de la cola (no bloqueante)."""
        if self.serial_conn is None or not self.serial_conn.is_open:
            if not self.reconectando:
                logging.warning("Conexión serial no disponible, intentando reconectar en hilo...")
                threading.Thread(target=self._intento_reconexion, daemon=True).start()
            return
        
        try:
            # Cola No Bloqueante
            if self.cola_comandos.full():
                self.cola_comandos.get()  # Descartar comando más antiguo
            self.cola_comandos.put((velocidad, angulo), block=False)
        except queue.Full:
            pass  # Cola llena, comando descartado (aceptable para control en tiempo real)

    def _worker_envio(self):
        """Worker que envía comandos desde la cola (optimización de rendimiento)."""
        while self.corriendo:
            try:
                # Obtener Comando de la Cola 
                velocidad, angulo = self.cola_comandos.get(timeout=0.05)
                comando = f"V:{velocidad};A:{angulo}\n"
                
                if self.serial_conn and self.serial_conn.is_open:
                    try:
                        self.serial_conn.write(comando.encode('utf-8'))
                        self.serial_conn.flush()
                    except serial.SerialException as e:
                        logging.error(f"Error al escribir en el puerto serial: {e}")
                        self.serial_conn.close()
                        self.serial_conn = None
            except queue.Empty:
                pass  # Timeout: continuar loop

    def _worker_telemetria(self):
        while self.corriendo:
            if self.serial_conn and self.serial_conn.is_open:
                try:
                    if self.serial_conn.in_waiting > 0:
                        linea = self.serial_conn.readline().decode('utf-8').strip()
                        if linea.startswith("T:"):
                            self.parsear_linea_telemetria(linea)
                except (serial.SerialException, UnicodeDecodeError, ValueError) as e:
                    logging.error(f"Error en worker de telemetría: {e}")
            time.sleep(0.01)

    def parsear_linea_telemetria(self, linea: str):
        try:
            match = TELEMETRIA_REGEX.search(linea)
            if match:
                z_val, ang_val, dist_val = match.groups()
                # Validar límites físicos antes de guardar
                angulo = int(ang_val)
                if 40 <= angulo <= 140:
                    with self.telemetria_lock:
                        self.latest_telemetria.update({
                            "z": float(z_val),
                            "angulo": angulo,
                            "dist_trasera": float(dist_val)
                        })
            else:
                logging.warning(f"Línea de telemetría corrupta o no reconocida: '{linea}'")
        except (ValueError, IndexError, AttributeError) as e:
            logging.error(f"Error al parsear línea de telemetría '{linea}': {e}")

    def obtener_telemetria(self) -> dict:
        with self.telemetria_lock:
            return dict(self.latest_telemetria)

    def esta_conectado(self) -> bool:
        # Verifica si la conexión serial está activa y abierta (interfaz pública).
        return self.serial_conn is not None and self.serial_conn.is_open

    def cerrar(self):
        self.corriendo = False
        if self.serial_conn and self.serial_conn.is_open:
            self.serial_conn.close()
            logging.info("Conexión serial cerrada correctamente.")


# ==================== LIDAR COMMUNICATION ====================

class TFLunaLidar:
    """
    Clase para interactuar con el sensor LiDAR TF-Luna a través de UART
    y controlar el servo SG90 sobre el cual está montado.
    """
    def __init__(self, port="/dev/serial0", baudrate=115200, pin_servo=18):
        self.port = port
        self.baudrate = baudrate
        self.pin_servo = pin_servo
        self.serial_conn = None
        self.servo = None
        self.conectar()
        self.angulo_actual = 90
        
    def conectar(self):
        try:
            self.serial_conn = serial.Serial(self.port, self.baudrate, timeout=0.1)
            logging.info(f"Conectado a LiDAR TF-Luna en {self.port}")
        except serial.SerialException as e:
            logging.error(f"Error al conectar con TF-Luna: {e}")
            self.serial_conn = None
        
        # Inicializar Servo SG90 
        try:
            # AngularServo usa ángulos en rango -90 a 90 grados
            # Mapeamos 0-180 a -90 a 90
            self.servo = AngularServo(self.pin_servo, min_angle=-90, max_angle=90, initial_angle=0)
            logging.info(f"Servo SG90 inicializado en GPIO {self.pin_servo}")
        except (GPIOZeroError, ValueError) as e:
            logging.error(f"Error al inicializar servo: {e}")
            self.servo = None

    def leer_distancia(self) -> float:
        """
        Lee el buffer del puerto serial y parsea la trama de 9 bytes del TF-Luna.
        Cabecera: 0x59 0x59
        Retorna la distancia en centímetros o -1.0 si hay un error/fuera de rango.
        TF-Luna no valida checksum por defecto, por lo que se ignora.
        """
        if not self.serial_conn or not self.serial_conn.is_open:
            return -1.0

        try:
            bytes_waiting = self.serial_conn.in_waiting
            if bytes_waiting >= 9:
                data = self.serial_conn.read(bytes_waiting)
                # Buscar header 0x59 0x59
                for i in range(len(data) - 8):
                    if data[i] == 0x59 and data[i+1] == 0x59:
                        # Extraer frame de 9 bytes
                        frame = data[i:i+9]
                        if len(frame) == 9:
                            # TF-Luna no valida checksum por defecto, ignorarlo
                            # Extraer distancia (bytes 2-3, little-endian)
                            dist_cm = struct.unpack('<H', frame[2:4])[0]
                            signal_quality = frame[1]
                            if signal_quality > 30:
                                return float(dist_cm)
        except (serial.SerialException, ValueError, IndexError) as e:
            logging.error(f"Error al leer TF-Luna: {e}")
            
        return -1.0

    def apuntar_servo(self, angulo: int):
        """
        Gira el servo SG90 al ángulo especificado (0 a 180).
        Usa gpiozero AngularServo para control por hardware PWM.
        """
        angulo = max(0, min(180, angulo))
        self.angulo_actual = angulo
        
        if self.servo:
            try:
                # Convertir 0-180 a -90 a 90 para gpiozero
                angulo_gpio = angulo - 90
                self.servo.angle = angulo_gpio
                logging.debug(f"Servo movido a {angulo} grados")
            except (GPIOZeroError, ValueError) as e:
                logging.error(f"Error al mover servo: {e}")

    def escanear_entorno(self, angulo_inicio=45, angulo_fin=135, paso=15, target_hz=10) -> list:
        """
        Realiza un barrido con el servo y toma mediciones en cada paso.
        Retorna una lista de tuplas: [(angulo, distancia), ...]
        Con rate limiting para consistencia.
        """
        period = 1.0 / target_hz
        mapa = []
        angulo_prev = self.angulo_actual  # posición inicial antes del barrido
        for ang in range(angulo_inicio, angulo_fin + 1, paso):
            t_start = time.monotonic()
            prev = angulo_prev
            angulo_prev = ang
            self.apuntar_servo(ang)
            # Asentamiento dinámico: mínimo 80ms + ~4ms por grado (SG90: ~60°/100ms)
            settling_ms = max(80, abs(ang - prev) * 4)
            time.sleep(settling_ms / 1000.0)
            dist = self.leer_distancia()
            mapa.append((ang, dist))

            # Rate limiting para consistencia
            elapsed = time.monotonic() - t_start
            sleep_time = period - elapsed
            if sleep_time > 0:
                time.sleep(sleep_time)
        return mapa
    
    def cerrar(self):
        # Cierra la conexión serial y libera el servo.
        if self.serial_conn and self.serial_conn.is_open:
            self.serial_conn.close()
            logging.info("Conexión LiDAR cerrada.")
        if self.servo:
            self.servo.close()
            logging.info("Servo liberado.")
