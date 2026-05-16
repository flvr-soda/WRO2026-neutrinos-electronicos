import time
import logging
from .fsm import Estado

class EstadoInicio(Estado):
    def enter(self, contexto: dict):
        super().enter(contexto)
        logging.info("Inicializando sistemas... (Espera simulada de 2 segundos)")
        time.sleep(2)

    def ejecutar(self, contexto: dict) -> str:
        # En el futuro, aquí se podría esperar a presionar un botón físico
        # o validar que todos los sensores estén listos.
        logging.info("Sistemas listos. Comenzando ronda.")
        return "NAVEGACION"

    def exit(self, contexto: dict):
        super().exit(contexto)
