import serial
import time
import logging
import struct
from gpiozero import AngularServo, GPIOZeroError

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
