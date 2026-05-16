import cv2
import time
import logging
import sys
from src.config_loader import ConfigLoader
from src.comms_arduino import ArduinoComms
from src.vision import VisionProcessor

logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')

def main():
    logging.info("Iniciando Sistema Terreneitor WRO 2026 MVP")
    
    # 1. Cargar configuración
    config_loader = ConfigLoader("config.yaml")
    if not config_loader.config:
        logging.critical("No se pudo cargar la configuración. Saliendo...")
        sys.exit(1)
        
    velocidades = config_loader.get_velocidades()
    angulos = config_loader.get_angulos_servo()
    
    # 2. Inicializar Comunicaciones
    arduino = ArduinoComms(port="/dev/ttyUSB0", baudrate=115200)
    
    # 3. Inicializar Procesamiento de Visión
    vision = VisionProcessor(config_loader)
    
    # 4. Inicializar Cámara (0 por defecto, ajusta según corresponda)
    cap = cv2.VideoCapture(0)
    if not cap.isOpened():
        logging.warning("No se pudo abrir la cámara, se ejecutará en modo simulado o sin video.")
        # Aquí podrías cargar un video de prueba si es necesario.
        
    try:
        while True:
            # Leer frame de la cámara
            ret, frame = cap.read()
            if not ret:
                logging.error("No se pudo leer el frame. Reintentando...")
                time.sleep(0.1)
                continue
            
            # Detectar color
            evento_color = vision.procesar_frame(frame)
            
            # Decidir velocidad y ángulo
            if evento_color == "ROJO":
                vel = velocidades.get("evasion", 40)
                ang = angulos.get("evasion_roja", 130) # Evasión izquierda
            elif evento_color == "VERDE":
                vel = velocidades.get("evasion", 40)
                ang = angulos.get("evasion_verde", 50) # Evasión derecha
            else:
                vel = velocidades.get("crucero", 60)
                ang = angulos.get("recto", 90)
                
            # Enviar comando al Arduino
            arduino.enviar_comando(vel, ang)
            
            # Pequeña pausa para no saturar CPU y el puerto serial
            time.sleep(0.05)
            
    except KeyboardInterrupt:
        logging.info("Interrupción por teclado (Ctrl+C). Deteniendo...")
    finally:
        # Apagar motores
        if arduino.serial_conn and arduino.serial_conn.is_open:
            arduino.enviar_comando(0, angulos.get("recto", 90))
        cap.release()
        logging.info("Sistema apagado de forma segura.")

if __name__ == "__main__":
    main()
