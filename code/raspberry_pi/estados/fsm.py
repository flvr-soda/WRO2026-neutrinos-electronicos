import logging
import time
import sched

class Estado:
    """Clase base abstracta para todos los estados del robot."""
    def enter(self, contexto: dict):
        """Se ejecuta al entrar al estado."""
        logging.info(f"Entrando al estado: {self.__class__.__name__}")

    def ejecutar(self, contexto: dict) -> str:
        """Lógica principal del estado. Debe retornar el nombre del siguiente estado."""
        raise NotImplementedError("El método ejecutar() debe ser implementado.")

    def exit(self, contexto: dict):
        """Se ejecuta antes de salir del estado."""
        pass


class MaquinaDeEstados:
    def __init__(self, contexto: dict):
        self.estados = {}
        self.estado_actual = None
        self.contexto = contexto
        # Planificador de tareas de la biblioteca estándar
        self.scheduler = sched.scheduler(time.monotonic, time.sleep)
        self.fsm_rate_hz = 50
        self.period = 1.0 / self.fsm_rate_hz
        self.corriendo = False

    def agregar_estado(self, nombre: str, estado: Estado):
        self.estados[nombre] = estado

    def set_estado_inicial(self, nombre: str):
        if nombre in self.estados:
            self.estado_actual = self.estados[nombre]
            self.estado_actual.enter(self.contexto)
        else:
            logging.error(f"Estado inicial '{nombre}' no registrado.")

    def _tick_ciclo(self):
        """Ejecuta una iteración del ciclo de vida y agenda el siguiente paso."""
        if not self.corriendo or self.estado_actual is None:
            return

        t_inicio = time.monotonic()

        # Ejecutar lógica del estado actual
        siguiente_estado_nombre = self.estado_actual.ejecutar(self.contexto)

        # Condición de salida limpia
        if siguiente_estado_nombre == "SALIR":
            self.estado_actual.exit(self.contexto)
            logging.info("Máquina de estados finalizada.")
            self.corriendo = False
            return

        # Transicionar a otro estado si se solicita
        if siguiente_estado_nombre and siguiente_estado_nombre != self._obtener_nombre_estado(self.estado_actual):
            if siguiente_estado_nombre in self.estados:
                self.estado_actual.exit(self.contexto)
                self.estado_actual = self.estados[siguiente_estado_nombre]
                self.estado_actual.enter(self.contexto)
            else:
                logging.error(f"Se intentó transicionar a un estado desconocido: '{siguiente_estado_nombre}'")

        # Agendar el siguiente ciclo compensando el tiempo de ejecución del tick actual
        t_fin = time.monotonic()
        tiempo_ejecucion = t_fin - t_inicio
        delay_siguiente = max(0.0, self.period - tiempo_ejecucion)
        
        if self.corriendo:
            self.scheduler.enter(delay_siguiente, 1, self._tick_ciclo)

    def run(self):
        """Ciclo de vida principal. Regula la frecuencia utilizando sched."""
        if self.estado_actual is None:
            logging.error("No se ha definido un estado inicial.")
            return

        self.corriendo = True
        # Agendar el primer tick de ejecución inmediata
        self.scheduler.enter(0, 1, self._tick_ciclo)
        
        # Bloquear e iniciar el planificador de eventos
        try:
            self.scheduler.run()
        except KeyboardInterrupt:
            self.corriendo = False
            raise

    def _obtener_nombre_estado(self, estado: Estado) -> str:
        for nombre, est in self.estados.items():
            if est == estado:
                return nombre
        return ""

