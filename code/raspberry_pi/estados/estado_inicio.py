import time
import logging
from .fsm import Estado
from gpiozero import Button, GPIOZeroError

class EstadoInicio(Estado):
    def __init__(self):
        super().__init__()
        self.boton_inicio = None
        self.estado_anterior_boton = None  # Para detectar cambios de estado (toggle)

    def enter(self, contexto: dict):
        super().enter(contexto)
        logging.info("Inicializando sistemas...")
        
        # --- Configuración del Pulsador de Retención de Inicio ---
        config_loader = contexto.get("config_loader")
        hardware_config = config_loader.get_hardware() if config_loader else {}
        pin_boton = hardware_config.get("pin_boton_inicio", 17)
        
        # --- Inicializar Botón GPIO (Regla 9.11) ---
        try:
            self.boton_inicio = Button(pin_boton, pull_up=True)
            self.estado_anterior_boton = self.boton_inicio.is_pressed
            logging.info(f"Pulsador de retención configurado en GPIO {pin_boton}")
            logging.info(f"Estado inicial: {'ON' if not self.estado_anterior_boton else 'OFF'}")
        except (GPIOZeroError, ValueError) as e:
            logging.error(f"Error al inicializar botón GPIO: {e}")
            logging.warning("Usando modo degradado: espera de teclado")
            self.boton_inicio = None
        
        time.sleep(1)  # Espera breve para estabilización del GPIO
        logging.info("Sistemas listos. Esperando cambio en el pulsador de retención...")

    def ejecutar(self, contexto: dict) -> str:
        # --- Esperar Pulsador de Retención Físico (Regla 9.11) ---
        if self.boton_inicio is not None:
            # Detectar cambio de estado (toggle) del switch
            estado_actual = self.boton_inicio.is_pressed
            if estado_actual != self.estado_anterior_boton:
                logging.info(f"Pulsador de retención cambiado de estado. Nuevo estado: {'ON' if not estado_actual else 'OFF'}. Iniciando ronda.")
                self.estado_anterior_boton = estado_actual
                return "NAVEGACION"
            else:
                return "INICIO"  # Mantener en espera
        else:
            # --- Modo Degradado: Entrada por Teclado ---
            logging.warning("Botón GPIO no disponible. Presione ENTER para iniciar...")
            try:
                input()  # Esperar ENTER
                logging.info("Inicio por teclado detectado. Iniciando ronda.")
                return "NAVEGACION"
            except (KeyboardInterrupt, EOFError):
                return "INICIO"

    def exit(self, contexto: dict):
        super().exit(contexto)
        # --- Transferir botón al contexto para reutilizar como parada de emergencia ---
        # No se cierra aquí; el ciclo de vida lo gestiona el contexto global
        if self.boton_inicio is not None:
            contexto["boton_parada"] = self.boton_inicio
            logging.info("Botón transferido al contexto como botón de parada.")
        self.boton_inicio = None
