import logging
import time
import serial
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
            if arduino and arduino.esta_conectado():
                arduino.enviar_comando(0, angulos.get("recto", 90))
        except (serial.SerialException, AttributeError) as e:
            logging.error(f"Error al enviar comando de detención: {e}")
            
        logging.info("Motores detenidos. Carrera finalizada.")
        
        # --- Salir de la FSM ---
        return "SALIR"

    def exit(self, contexto: dict):
        super().exit(contexto)
