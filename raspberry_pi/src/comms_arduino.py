import serial
import time
import logging
import threading

class ArduinoComms:
    def __init__(self, port="/dev/ttyUSB0", baudrate=115200):
        self.port = port
        self.baudrate = baudrate
        self.serial_conn = None
        self.reconectando = False
        self.corriendo = True
        
        self.telemetria_lock = threading.Lock()
        self.latest_telemetria = {
            "rpm": 0,
            "cms": 0,
            "angulo": 90
        }
        
        self.conectar()
        
        # Iniciar hilo de lectura de telemetría
        self.hilo_telemetria = threading.Thread(target=self._worker_telemetria, daemon=True)
        self.hilo_telemetria.start()

    def conectar(self):
        try:
            self.serial_conn = serial.Serial(self.port, self.baudrate, timeout=1)
            time.sleep(2) # Esperar a que el Arduino se reinicie
            logging.info(f"Conectado a Arduino en {self.port} a {self.baudrate} baudios.")
        except serial.SerialException as e:
            logging.error(f"No se pudo conectar al puerto serial {self.port}: {e}")
            self.serial_conn = None

    def _intento_reconexion(self):
        self.reconectando = True
        time.sleep(2)  # Pequeño backoff
        self.conectar()
        self.reconectando = False

    def enviar_comando(self, velocidad: int, angulo: int):
        if self.serial_conn is None or not self.serial_conn.is_open:
            if not self.reconectando:
                logging.warning("Conexión serial no disponible, intentando reconectar en hilo...")
                threading.Thread(target=self._intento_reconexion, daemon=True).start()
            return
            
        comando = f"V:{velocidad};A:{angulo}\n"
        try:
            self.serial_conn.write(comando.encode('utf-8'))
            self.serial_conn.flush()
        except serial.SerialException as e:
            logging.error(f"Error al escribir en el puerto serial: {e}")
            self.serial_conn.close()
            self.serial_conn = None

    def _worker_telemetria(self):
        while self.corriendo:
            if self.serial_conn and self.serial_conn.is_open:
                try:
                    if self.serial_conn.in_waiting > 0:
                        linea = self.serial_conn.readline().decode('utf-8').strip()
                        if linea.startswith("T:"):
                            self.parsear_linea_telemetria(linea)
                except Exception as e:
                    logging.error(f"Error en worker de telemetría: {e}")
            time.sleep(0.01)

    def parsear_linea_telemetria(self, linea: str):
        try:
            partes = linea.split(";")
            datos = {}
            for parte in partes:
                if not parte or parte == "T:":
                    continue
                if parte.startswith("T:"):
                    parte = parte[2:]
                if ":" in parte:
                    clave, valor = parte.split(":", 1)
                    datos[clave.lower()] = int(valor)
            
            with self.telemetria_lock:
                self.latest_telemetria.update(datos)
        except Exception as e:
            logging.error(f"Error al parsear línea de telemetría '{linea}': {e}")

    def obtener_telemetria(self) -> dict:
        with self.telemetria_lock:
            return dict(self.latest_telemetria)

    def cerrar(self):
        self.corriendo = False
        if self.serial_conn and self.serial_conn.is_open:
            self.serial_conn.close()
            logging.info("Conexión serial cerrada correctamente.")
