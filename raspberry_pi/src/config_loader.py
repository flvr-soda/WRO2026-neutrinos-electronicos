import yaml
import logging
import os

class ConfigLoader:
    def __init__(self, config_filename="config.yaml"):
        # Usar ruta absoluta basada en la ubicación de este script
        base_dir = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
        self.config_path = os.path.join(base_dir, config_filename)
        self.config = {}
        self.load_config()
        self.validate()

    def load_config(self):
        try:
            with open(self.config_path, 'r') as file:
                self.config = yaml.safe_load(file)
                if self.config is None:
                    self.config = {}
                logging.info(f"Configuración cargada correctamente desde {self.config_path}")
        except FileNotFoundError:
            logging.error(f"El archivo {self.config_path} no fue encontrado.")
            self.config = {}
        except yaml.YAMLError as exc:
            logging.error(f"Error al parsear el archivo YAML: {exc}")
            self.config = {}

    def validate(self):
        """Valida que la configuración cargada tenga los rangos correctos."""
        # Validar velocidades
        if 'velocidades' in self.config:
            for k, v in self.config['velocidades'].items():
                if not (0 <= v <= 255):
                    logging.warning(f"Velocidad '{k}'={v} fuera de rango (0-255). Ajustando...")
                    self.config['velocidades'][k] = max(0, min(255, v))
        
        # Validar ángulos
        if 'angulos_servo' in self.config:
            for k, v in self.config['angulos_servo'].items():
                if not (40 <= v <= 140): # Rango de seguridad de motores.cpp
                    logging.warning(f"Ángulo '{k}'={v} fuera de rango seguro (40-140). Ajustando...")
                    self.config['angulos_servo'][k] = max(40, min(140, v))

        # Validar valores por defecto para competicion
        comp = self.config.setdefault('competicion', {})
        comp.setdefault('modo_reto', 'obstaculos')
        comp.setdefault('sentido_giro', 'horario')
        comp.setdefault('max_vueltas', 3)

    def get_velocidades(self):
        return self.config.get('velocidades', {})

    def get_angulos_servo(self):
        return self.config.get('angulos_servo', {})

    def get_hsv_rojo(self):
        return self.config.get('hsv_rojo', {})

    def get_hsv_verde(self):
        return self.config.get('hsv_verde', {})

    def get_hsv_magenta(self):
        return self.config.get('hsv_magenta', {})

    def get_competicion(self):
        return self.config.get('competicion', {})

    def get_hardware(self):
        return self.config.get('hardware', {})

    def get_vision(self):
        return self.config.get('vision', {})

    def get_lidar(self):
        return self.config.get('lidar', {})

