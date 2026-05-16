import logging
from .fsm import Estado

class EstadoEstacionar(Estado):
    def enter(self, contexto: dict):
        super().enter(contexto)
        logging.info("Maniobra de parqueo iniciada (DUMMY).")

    def ejecutar(self, contexto: dict) -> str:
        # Aquí irá la lógica futura del TF-Luna para el parqueo paralelo
        logging.info("Parqueo completado.")
        return "FIN"

    def exit(self, contexto: dict):
        super().exit(contexto)
