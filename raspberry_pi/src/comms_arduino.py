import serial
import time
import logging

class ArduinoComms:
    def __init__(self, port="/dev/ttyUSB0", baudrate=115200):
        self.port = port
        self.baudrate = baudrate
        self.serial_conn = None
        self.conectar()

    def conectar(self):
        try:
            self.serial_conn = serial.Serial(self.port, self.baudrate, timeout=1)
            time.sleep(2) # Esperar a que el Arduino se reinicie
            logging.info(f"Conectado a Arduino en {self.port} a {self.baudrate} baudios.")
        except serial.SerialException as e:
            logging.error(f"No se pudo conectar al puerto serial {self.port}: {e}")
            self.serial_conn = None

    def enviar_comando(self, velocidad: int, angulo: int):
        if self.serial_conn is None or not self.serial_conn.is_open:
            logging.warning("Conexión serial no disponible, intentando reconectar...")
            self.conectar()
            
        if self.serial_conn and self.serial_conn.is_open:
            comando = f"V:{velocidad};A:{angulo}\n"
            try:
                self.serial_conn.write(comando.encode('utf-8'))
                self.serial_conn.flush()
                # logging.debug(f"Comando enviado: {comando.strip()}")
            except serial.SerialException as e:
                logging.error(f"Error al escribir en el puerto serial: {e}")
                self.serial_conn.close()
                self.serial_conn = None
