import cv2
import logging
import sys
import time

# Importar configuraciones y utilidades de hardware
from src.config import (
    get_velocidades, get_angulos_servo, get_lidar, get_vision, get_competicion,
    get_vehiculo, get_hardware, get_serial_ports, get_hsv_rojo, get_hsv_verde, get_hsv_magenta
)
from src.comms import ArduinoComms, TFLunaLidar
from src.vision import VisionProcessor
from src.hardware import MockCamera

# Intentar importar RPi.GPIO para limpieza de GPIO
try:
    import RPi.GPIO as GPIO
    GPIO_AVAILABLE = True
except ImportError:
    GPIO_AVAILABLE = False
    GPIO = None


class MockCameraAdapter:
    """Adapter to make MockCamera compatible with cv2.VideoCapture interface"""
    def __init__(self, mock_camera):
        self.mock_camera = mock_camera
        self._is_opened = True
    
    def read(self):
        """Returns (True, frame) like cv2.VideoCapture.read()"""
        frame = self.mock_camera.capture_frame()
        if frame is not None:
            return True, frame
        return False, None
    
    def isOpened(self):
        """Returns True if camera is available"""
        return self._is_opened
    
    def set(self, prop_id, value):
        """Mock implementation of cv2.VideoCapture.set()"""
        # MockCamera doesn't support these properties, but we ignore them
        pass
    
    def release(self):
        """Mock implementation of cv2.VideoCapture.release()"""
        self.mock_camera.stop()
        self._is_opened = False

# Importar la Máquina de Estados y sus Estados Concretos
from .estados import MaquinaDeEstados, EstadoInicio, EstadoNavegacion, EstadoEstacionar, EstadoFin

logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')

def main():
    logging.info("Iniciando Sistema Terreneitor WRO 2026 MVP (FSM Modular)")
    
    # Limpiar GPIO al inicio para evitar conflictos con ejecuciones anteriores
    if GPIO_AVAILABLE:
        try:
            GPIO.cleanup()
            logging.info("GPIO limpiado al inicio")
        except Exception as e:
            logging.warning(f"Error limpiando GPIO al inicio: {e}")
    
    # 1. Cargar configuración directamente
    velocidades = get_velocidades()
    angulos = get_angulos_servo()
    
    # 2. Inicializar hardware y componentes
    arduino = ArduinoComms(baudrate=115200)
    vision = VisionProcessor(get_hsv_rojo, get_hsv_verde, get_hsv_magenta, get_vision)

    # Esperar telemetría inicial del Arduino para verificar sensores
    logging.info("Esperando telemetría del Arduino para verificar sensores...")
    time.sleep(2)  # Esperar 2 segundos para que Arduino envíe telemetría
    telemetria = arduino.obtener_telemetria()

    # Obtener configuración del LiDAR
    lidar_config = get_lidar()
    pin_servo = lidar_config.get("pin_servo", 18)
    serial_ports = get_serial_ports()
    lidar_port = serial_ports.get("lidar", "/dev/serial0")
    lidar = TFLunaLidar(port=lidar_port, baudrate=115200, pin_servo=pin_servo)

    # Inicializar cámara USB con cv2.VideoCapture
    vision_config = get_vision()
    camera_index = vision_config.get("camera_index", 0)
    cap = cv2.VideoCapture(camera_index)

    if not cap.isOpened():
        logging.warning(f"No se pudo abrir la cámara USB en índice {camera_index}, usando MockCamera")
        mock_cam = MockCamera()
        mock_cam.setup(vision_config.get("width", 640), vision_config.get("height", 480))
        cap = MockCameraAdapter(mock_cam)
    else:
        # Configurar resolución
        cap.set(cv2.CAP_PROP_FRAME_WIDTH, vision_config.get("width", 640))
        cap.set(cv2.CAP_PROP_FRAME_HEIGHT, vision_config.get("height", 480))

    # Logs de verificación de sensores
    logging.info("=== SENSORES ===")
    if isinstance(cap, MockCameraAdapter):
        status_cam = "MOCK"
    else:
        status_cam = "OK" if cap.isOpened() else "FAIL"
    status_ard = "OK" if arduino.esta_conectado() else "FAIL"
    status_lid = "OK" if lidar.serial_conn and lidar.serial_conn.is_open else "FAIL"
    status_servo = "OK" if lidar.servo is not None else "FAIL"
    logging.info(f"Cámara: {status_cam} | Arduino: {status_ard} | LiDAR: {status_lid} | Servo: {status_servo}")
    
    if arduino.esta_conectado():
        mpu_ok = "z" in telemetria
        servo_ok = 40 <= telemetria.get("angulo", 0) <= 270
        ultrasonido_ok = telemetria.get("dist_trasera", -1) >= 0
        logging.info(f"  MPU6050: {'OK' if mpu_ok else 'FAIL'} | Servo: {'OK' if servo_ok else 'FAIL'} | HC-SR04: {'OK' if ultrasonido_ok else 'FAIL'}")

    # 3. Construir el contexto global para la FSM
    contexto = {
        "config_loader": None,  # Ya no usamos ConfigLoader
        "velocidades": velocidades,
        "angulos": angulos,
        "arduino": arduino,
        "vision": vision,
        "lidar": lidar,
        "cap": cap  # Cámara USB cv2.VideoCapture
    }

    # 4. Inicializar y poblar la Máquina de Estados
    fsm = MaquinaDeEstados(contexto)
    fsm.agregar_estado("INICIO", EstadoInicio())
    fsm.agregar_estado("NAVEGACION", EstadoNavegacion())
    fsm.agregar_estado("ESTACIONAR", EstadoEstacionar())
    fsm.agregar_estado("FIN", EstadoFin())

    # 5. Configurar el estado de arranque
    fsm.set_estado_inicial("INICIO")

    # 6. Ciclo de ejecución
    try:
        fsm.run()
    except KeyboardInterrupt:
        logging.info("Interrupción por teclado (Ctrl+C). Forzando estado FIN...")
        # Instanciar el estado fin directamente como mecanismo de seguridad
        estado_emergencia = EstadoFin()
        estado_emergencia.enter(contexto)
        estado_emergencia.ejecutar(contexto)
        estado_emergencia.exit(contexto)
    finally:
        # Limpieza de recursos global
        if arduino:
            arduino.cerrar()
        if lidar:
            lidar.cerrar()
        if cap:
            cap.release()  # Works for both cv2.VideoCapture and MockCameraAdapter
        # Liberar botón GPIO si fue transferido al contexto
        boton = contexto.get("boton_parada")
        if boton:
            try:
                boton.close()
            except Exception as e:
                logging.warning(f"Error cerrando botón: {e}")
        # Limpiar todos los GPIO al final
        if GPIO_AVAILABLE:
            try:
                GPIO.cleanup()
                logging.info("GPIO limpiado al final")
            except Exception as e:
                logging.warning(f"Error limpiando GPIO al final: {e}")
        logging.info("Recursos de hardware liberados.")

if __name__ == "__main__":
    main()
