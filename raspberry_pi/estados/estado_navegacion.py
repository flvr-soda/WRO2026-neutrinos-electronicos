import time
import logging
from .fsm import Estado

class EstadoNavegacion(Estado):
    def enter(self, contexto: dict):
        super().enter(contexto)
        logging.info("Modo navegación autónoma iniciado.")

    def ejecutar(self, contexto: dict) -> str:
        # Recuperar dependencias del contexto
        cap = contexto.get("cap")
        vision = contexto.get("vision")
        arduino = contexto.get("arduino")
        velocidades = contexto.get("velocidades")
        angulos = contexto.get("angulos")

        if cap is None:
            logging.error("Cámara no disponible en contexto.")
            return "FIN"

        # Leer frame
        ret, frame = cap.read()
        if not ret:
            logging.error("No se pudo leer el frame en navegación. Reintentando...")
            time.sleep(0.1)
            return "NAVEGACION"

        # Detectar color
        evento_color = vision.procesar_frame(frame)
        
        # Lógica de evasión / navegación pura del MVP
        if evento_color == "ROJO":
            vel = velocidades.get("evasion", 40)
            ang = angulos.get("evasion_roja", 130) # Izquierda
        elif evento_color == "VERDE":
            vel = velocidades.get("evasion", 40)
            ang = angulos.get("evasion_verde", 50) # Derecha
        else:
            vel = velocidades.get("crucero", 60)
            ang = angulos.get("recto", 90)
            
        # Enviar comando
        if arduino:
            arduino.enviar_comando(vel, ang)
            
        # Pausa para no saturar CPU (mantener el loop estable a ~20 Hz)
        time.sleep(0.05)
        
        # En el MVP, nos quedamos en Navegación permanentemente
        # Hasta que se presione Ctrl+C o la lógica futura determine que terminó la pista
        return "NAVEGACION"

    def exit(self, contexto: dict):
        super().exit(contexto)
