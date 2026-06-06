import serial
import time
import logging
import threading
from queue import Queue

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
            "dist": 0,
            "angulo": 90
        }
        
        # --- Cola de Comandos para Envío Asíncrono ---
        self.cola_comandos = Queue(maxsize=10)
        
        self.conectar()
        
        # --- Iniciar Hilo de Lectura de Telemetría ---
        self.hilo_telemetria = threading.Thread(target=self._worker_telemetria, daemon=True)
        self.hilo_telemetria.start()
        
        # --- Iniciar Hilo de Envío de Comandos ---
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
            # --- Cola No Bloqueante ---
            if self.cola_comandos.full():
                self.cola_comandos.get()  # Descartar comando más antiguo
            self.cola_comandos.put((velocidad, angulo), block=False)
        except:
            pass  # Cola llena, comando descartado (aceptable para control en tiempo real)

    def _worker_envio(self):
        """Worker que envía comandos desde la cola (optimización de rendimiento)."""
        while self.corriendo:
            try:
                # --- Obtener Comando de la Cola ---
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
            except:
            pass  # Timeout: continuar loop

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
                    valor_int = int(valor)
                    
                    # --- Validación de Rangos (Robustez) ---
                    if clave.lower() == "rpm":
                        # RPM razonable: 0 a 5000
                        if 0 <= valor_int <= 5000:
                            datos[clave.lower()] = valor_int
                    elif clave.lower() == "cms":
                        # Velocidad en cm/s razonable: 0 a 200
                        if 0 <= valor_int <= 200:
                            datos[clave.lower()] = valor_int
                    elif clave.lower() == "dist":
                        # Distancia acumulada razonable: 0 a 100000 cm (1 km)
                        if 0 <= valor_int <= 100000:
                            datos[clave.lower()] = valor_int
                    elif clave.lower() == "a":
                        # Ángulo razonable: 40 a 140 (rango seguro de motores.cpp)
                        if 40 <= valor_int <= 140:
                            datos[clave.lower()] = valor_int
                    else:
                        # Otros campos: aceptar sin validación específica
                        datos[clave.lower()] = valor_int
            
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
