import logging

class Estado:
    """Clase base abstracta para todos los estados del robot."""
    def enter(self, contexto: dict):
        """Se ejecuta al entrar al estado."""
        logging.info(f"--- Entrando al estado: {self.__class__.__name__} ---")

    def ejecutar(self, contexto: dict) -> str:
        """
        Lógica principal del estado.
        Debe retornar el nombre del siguiente estado en formato String.
        """
        raise NotImplementedError("El método ejecutar() debe ser implementado.")

    def exit(self, contexto: dict):
        """Se ejecuta antes de salir del estado."""
        pass


class MaquinaDeEstados:
    def __init__(self, contexto: dict):
        self.estados = {}
        self.estado_actual = None
        self.contexto = contexto

    def agregar_estado(self, nombre: str, estado: Estado):
        self.estados[nombre] = estado

    def set_estado_inicial(self, nombre: str):
        if nombre in self.estados:
            self.estado_actual = self.estados[nombre]
            self.estado_actual.enter(self.contexto)
        else:
            logging.error(f"Estado inicial '{nombre}' no registrado.")

    def run(self):
        """
        Ciclo de vida principal. Ejecuta el estado actual y realiza la transición
        si el estado retorna un nuevo nombre.
        """
        if self.estado_actual is None:
            logging.error("No se ha definido un estado inicial.")
            return

        # La máquina de estados principal correrá en este bucle
        while True:
            # Ejecutamos la lógica del estado actual
            siguiente_estado_nombre = self.estado_actual.ejecutar(self.contexto)
            
            # Condición de salida limpia
            if siguiente_estado_nombre == "SALIR":
                self.estado_actual.exit(self.contexto)
                logging.info("Máquina de estados finalizada.")
                break

            # Si el estado nos pide transicionar a otro diferente
            if siguiente_estado_nombre and siguiente_estado_nombre != self._obtener_nombre_estado(self.estado_actual):
                if siguiente_estado_nombre in self.estados:
                    self.estado_actual.exit(self.contexto)
                    self.estado_actual = self.estados[siguiente_estado_nombre]
                    self.estado_actual.enter(self.contexto)
                else:
                    logging.error(f"Se intentó transicionar a un estado desconocido: '{siguiente_estado_nombre}'")

    def _obtener_nombre_estado(self, estado: Estado) -> str:
        for nombre, est in self.estados.items():
            if est == estado:
                return nombre
        return ""
