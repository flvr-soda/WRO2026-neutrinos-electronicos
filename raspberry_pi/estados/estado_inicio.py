import time
import logging
from .fsm import Estado
from gpiozero import Button

class EstadoInicio(Estado):
    def __init__(self):
        super().__init__()
        self.boton_inicio = None

    def enter(self, contexto: dict):
        super().enter(contexto)
        logging.info("Inicializando sistemas...")
        
        # --- Configuración del Botón de Inicio ---
        config_loader = contexto.get("config_loader")
        hardware_config = config_loader.get_hardware() if config_loader else {}
        pin_boton = hardware_config.get("pin_boton_inicio", 17)
        
        # --- Inicializar Botón GPIO (Regla 9.11) ---
        try:
            self.boton_inicio = Button(pin_boton, pull_up=True)
            logging.info(f"Botón de inicio configurado en GPIO {pin_boton}")
        except Exception as e:
            logging.error(f"Error al inicializar botón GPIO: {e}")
            logging.warning("Usando modo degradado: espera de teclado")
            self.boton_inicio = None
        
        time.sleep(1)  # Espera breve para estabilización del GPIO
        logging.info("Sistemas listos. Esperando botón de inicio...")

    def ejecutar(self, contexto: dict) -> str:
        # --- Esperar Botón de Inicio Físico (Regla 9.11) ---
        if self.boton_inicio is not None:
            if self.boton_inicio.is_pressed:
                logging.info("Botón de inicio presionado. Iniciando ronda.")
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
            except:
                return "INICIO"

    def exit(self, contexto: dict):
        super().exit(contexto)
        # --- Liberar Recursos del Botón ---
        if self.boton_inicio is not None:
            self.boton_inicio.close()
            self.boton_inicio = None
