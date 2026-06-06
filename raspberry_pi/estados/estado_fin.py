import logging
import time
from .fsm import Estado

class EstadoFin(Estado):
    def enter(self, contexto: dict):
        super().enter(contexto)
        logging.info("Secuencia de finalización activada.")

    def ejecutar(self, contexto: dict) -> str:
        arduino = contexto.get("arduino")
        angulos = contexto.get("angulos", {})
        
        # --- Detener Motores y Centrar Servo ---
        try:
            if arduino and arduino.serial_conn and arduino.serial_conn.is_open:
                arduino.enviar_comando(0, angulos.get("recto", 90))
        except Exception as e:
            logging.error(f"Error al enviar comando de detención: {e}")
            
        logging.info("Motores detenidos. Carrera finalizada.")
        
        # --- Salir de la FSM ---
        return "SALIR"

    def exit(self, contexto: dict):
        super().exit(contexto)
