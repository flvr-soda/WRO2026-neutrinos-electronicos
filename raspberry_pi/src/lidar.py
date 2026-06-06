import serial
import time
import logging
from gpiozero import AngularServo

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
        
        # --- Inicializar Servo SG90 ---
        try:
            # AngularServo usa ángulos en rango -90 a 90 grados
            # Mapeamos 0-180 a -90 a 90
            self.servo = AngularServo(self.pin_servo, min_angle=-90, max_angle=90, initial_angle=0)
            logging.info(f"Servo SG90 inicializado en GPIO {self.pin_servo}")
        except Exception as e:
            logging.error(f"Error al inicializar servo: {e}")
            self.servo = None

    def leer_distancia(self) -> float:
        """
        Lee el buffer del puerto serial y parsea la trama de 9 bytes del TF-Luna.
        Cabecera: 0x59 0x59
        Retorna la distancia en centímetros o -1.0 si hay un error/fuera de rango.
        """
        if not self.serial_conn or not self.serial_conn.is_open:
            return -1.0

        try:
            # --- Buscar Inicio de Trama (0x59, 0x59) ---
            max_intentos = 50
            intentos = 0
            while intentos < max_intentos:
                intentos += 1
                if self.serial_conn.in_waiting >= 9:
                    # --- Leer Byte de Cabecera ---
                    b1 = self.serial_conn.read(1)
                    if b1 == b'\x59':
                        b2 = self.serial_conn.read(1)
                        if b2 == b'\x59':
                            # --- Leer Datos de Trama (7 bytes) ---
                            datos = self.serial_conn.read(7)
                            if len(datos) == 7:
                                # Distancia = bytes 0 y 1 (Dist_L y Dist_H)
                                distancia_cm = datos[0] + (datos[1] << 8)
                                # Fuerza de señal (Strength) en bytes 2 y 3
                                strength = datos[2] + (datos[3] << 8)
                                
                                # Si la fuerza es muy baja, la lectura no es confiable
                                if strength < 100:
                                    return -1.0
                                    
                                return float(distancia_cm)
                else:
                    break
        except Exception as e:
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
                # --- Convertir 0-180 a -90 a 90 para gpiozero ---
                angulo_gpio = angulo - 90
                self.servo.angle = angulo_gpio
                logging.debug(f"Servo movido a {angulo} grados")
            except Exception as e:
                logging.error(f"Error al mover servo: {e}")

    def escanear_entorno(self, angulo_inicio=45, angulo_fin=135, paso=15) -> list:
        """
        Realiza un barrido con el servo y toma mediciones en cada paso.
        Retorna una lista de tuplas: [(angulo, distancia), ...]
        Optimizado: reducido tiempo de sleep de 0.15s a 0.08s para mejorar rendimiento.
        """
        mapa = []
        for ang in range(angulo_inicio, angulo_fin + 1, paso):
            self.apuntar_servo(ang)
            time.sleep(0.08)  # Reducido de 0.15s (optimización de rendimiento)
            dist = self.leer_distancia()
            mapa.append((ang, dist))
        return mapa
    
    def cerrar(self):
        """Cierra la conexión serial y libera el servo."""
        if self.serial_conn and self.serial_conn.is_open:
            self.serial_conn.close()
            logging.info("Conexión LiDAR cerrada.")
        if self.servo:
            self.servo.close()
            logging.info("Servo liberado.")
