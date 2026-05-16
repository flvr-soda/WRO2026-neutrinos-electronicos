import logging
import time
from .fsm import Estado

class EstadoFin(Estado):
    def enter(self, contexto: dict):
        super().enter(contexto)
        logging.info("Secuencia de finalización activada.")

    def ejecutar(self, contexto: dict) -> str:
        arduino = contexto.get("arduino")
        angulos = contexto.get("angulos")
        
        # Detener inmediatamente motores y centrar servo
        if arduino and arduino.serial_conn and arduino.serial_conn.is_open:
            arduino.enviar_comando(0, angulos.get("recto", 90))
            
        logging.info("Motores detenidos. Carrera finalizada.")
        
        # Se requiere salir de la FSM
        return "SALIR"

    def exit(self, contexto: dict):
        super().exit(contexto)
