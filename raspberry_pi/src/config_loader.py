import yaml
import logging

class ConfigLoader:
    def __init__(self, config_path="config.yaml"):
        self.config_path = config_path
        self.config = {}
        self.load_config()

    def load_config(self):
        try:
            with open(self.config_path, 'r') as file:
                self.config = yaml.safe_load(file)
                logging.info(f"Configuración cargada correctamente desde {self.config_path}")
        except FileNotFoundError:
            logging.error(f"El archivo {self.config_path} no fue encontrado.")
            self.config = {}
        except yaml.YAMLError as exc:
            logging.error(f"Error al parsear el archivo YAML: {exc}")
            self.config = {}

    def get_velocidades(self):
        return self.config.get('velocidades', {})

    def get_angulos_servo(self):
        return self.config.get('angulos_servo', {})

    def get_hsv_rojo(self):
        return self.config.get('hsv_rojo', {})

    def get_hsv_verde(self):
        return self.config.get('hsv_verde', {})
