import cv2
import logging
import sys

# Importar configuraciones y utilidades de hardware
from src.config import (
    get_velocidades, get_angulos_servo, get_lidar, get_vision, get_competicion,
    get_vehiculo, get_hardware, get_serial_ports, get_hsv_rojo, get_hsv_verde, get_hsv_magenta
)
from src.comms import ArduinoComms, TFLunaLidar
from src.vision import VisionProcessor

# Importar la Máquina de Estados y sus Estados Concretos
from estados import MaquinaDeEstados, EstadoInicio, EstadoNavegacion, EstadoEstacionar, EstadoFin

logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')

def main():
    logging.info("Iniciando Sistema Terreneitor WRO 2026 MVP (FSM Modular)")
    
    # 1. Cargar configuración directamente
    velocidades = get_velocidades()
    angulos = get_angulos_servo()
    
    # 2. Inicializar hardware y componentes
    arduino = ArduinoComms(baudrate=115200)
    vision = VisionProcessor(get_hsv_rojo, get_hsv_verde, get_hsv_magenta, get_vision)

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
        logging.error(f"No se pudo abrir la cámara USB en índice {camera_index}")
        raise RuntimeError(f"Error al inicializar cámara USB en índice {camera_index}")
    
    # Configurar resolución
    cap.set(cv2.CAP_PROP_FRAME_WIDTH, vision_config.get("width", 640))
    cap.set(cv2.CAP_PROP_FRAME_HEIGHT, vision_config.get("height", 480))
    
    logging.info(f"Cámara USB inicializada en índice {camera_index}")

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
            cap.release()  # cv2.VideoCapture usa release()
        # Liberar botón GPIO si fue transferido al contexto
        boton = contexto.get("boton_parada")
        if boton:
            boton.close()
        logging.info("Recursos de hardware liberados.")

if __name__ == "__main__":
    main()
