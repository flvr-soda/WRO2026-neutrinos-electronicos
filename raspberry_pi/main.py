import cv2
import logging
import sys

# Importar configuraciones y utilidades de hardware
from src.config_loader import ConfigLoader
from src.comms_arduino import ArduinoComms
from src.vision import VisionProcessor
from src.lidar import TFLunaLidar

# Importar la Máquina de Estados y sus Estados Concretos
from estados import MaquinaDeEstados, EstadoInicio, EstadoNavegacion, EstadoEstacionar, EstadoFin

logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')

def main():
    logging.info("Iniciando Sistema Terreneitor WRO 2026 MVP (FSM Modular)")
    
    # 1. Cargar configuración
    config_loader = ConfigLoader("config.yaml")
    if not config_loader.config:
        logging.critical("No se pudo cargar la configuración. Saliendo...")
        sys.exit(1)
        
    velocidades = config_loader.get_velocidades()
    angulos = config_loader.get_angulos_servo()
    
    # 2. Inicializar hardware y componentes
    arduino = ArduinoComms(port="/dev/ttyUSB0", baudrate=115200)
    vision = VisionProcessor(config_loader)
    lidar = TFLunaLidar(port="/dev/serial0", baudrate=115200)
    
    cap = cv2.VideoCapture(0)
    if not cap.isOpened():
        logging.warning("No se pudo abrir la cámara, el procesamiento visual retornará 'NINGUNO'.")

    # 3. Construir el contexto global para la FSM
    contexto = {
        "config_loader": config_loader,
        "velocidades": velocidades,
        "angulos": angulos,
        "arduino": arduino,
        "vision": vision,
        "lidar": lidar,
        "cap": cap
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
        if cap:
            cap.release()
        logging.info("Recursos de hardware liberados.")

if __name__ == "__main__":
    main()
