import re
import time
import logging
import threading
import queue
import serial
import glob

# Expresión regular para parsear la telemetría: T:Z:<grados>;A:<angulo>;U:<dist_trasera>;
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
