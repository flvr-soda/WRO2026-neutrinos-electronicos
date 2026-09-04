import yaml
import logging
import os
from dataclasses import dataclass, field
from typing import Dict, Any, List

@dataclass
class VelocidadesConfig:
    crucero: int = 60
    evasion: int = 40
    crucero_cm_s: float = 30.0
    evasion_cm_s: float = 20.0

@dataclass
class AngulosServoConfig:
    recto: int = 90
    giro_derecha: int = 50
    giro_izquierda: int = 130

@dataclass
class HSVColorConfig:
    lower: List[int] = field(default_factory=list)
    upper: List[int] = field(default_factory=list)
    lower2: List[int] = field(default_factory=list)
    upper2: List[int] = field(default_factory=list)

@dataclass
class CompeticionConfig:
    modo_reto: str = "obstaculos"
    sentido_giro: str = "horario"
    max_vueltas: int = 3
    perimetro_pista_cm: float = 1200.0
    tiempo_limite_segundos: float = 180.0
    distancia_seccion_arranque_cm: float = 300.0
    retorno_arranque_habilitado: bool = True
    distancia_seccion_meta_cm: float = 300.0
    deteccion_violacion_senales: bool = True

@dataclass
class HardwareConfig:
    pin_boton_inicio: int = 17

@dataclass
class PIDConfig:
    kp: float = 1.2
    ki: float = 0.3
    kd: float = 0.05
    integral_max: float = 50.0

@dataclass
class VisionConfig:
    min_area: float = 500.0
    width: int = 640
    height: int = 480
    format: str = "RGB888"
    factor_px_cm: float = 0.5
    odometria_visual_habilitada: bool = True
    pid: PIDConfig = field(default_factory=PIDConfig)

@dataclass
class LidarConfig:
    pin_servo: int = 18
    distancia_giro_cm: float = 50.0
    umbral_hueco_cm: float = 40.0
    distancia_pared_cm: float = 30.0
    angulo_escaneo_inicio: int = 45
    angulo_escaneo_fin: int = 135
    paso_escaneo: int = 15

@dataclass
class VehiculoConfig:
    largo_cm: float = 27.0
    ancho_frente_cm: float = 15.0
    ancho_atras_cm: float = 17.0
    radio_giro_cm: float = 8.5

class ConfigLoader:
    def __init__(self, config_filename="config.yaml"):
        base_dir = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
        self.config_path = os.path.join(base_dir, config_filename)
        self.config = {}
        self.load_config()
        self.validate()

    def load_config(self):
        try:
            with open(self.config_path, 'r', encoding='utf-8') as file:
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

    def _validate_hsv(self, hsv_dict: Dict[str, Any], default_lower: List[int], default_upper: List[int], has_two_ranges: bool = False) -> Dict[str, Any]:
        result = {}
        for param, default in [('lower', default_lower), ('upper', default_upper), ('lower2', default_lower), ('upper2', default_upper)]:
            if not has_two_ranges and param in ['lower2', 'upper2']:
                continue
            val = hsv_dict.get(param, default)
            if isinstance(val, list) and len(val) == 3:
                val[0] = max(0, min(180, int(val[0])))
                val[1] = max(0, min(255, int(val[1])))
                val[2] = max(0, min(255, int(val[2])))
                result[param] = val
            else:
                result[param] = default
        return result

    def validate(self):
        """Valida e inicializa los esquemas de configuración usando clases de datos."""
        # 1. Velocidades
        vel_raw = self.config.get('velocidades', {})
        self.velocidades = VelocidadesConfig(
            crucero=int(max(0, min(100, vel_raw.get('crucero', 60)))),
            evasion=int(max(0, min(100, vel_raw.get('evasion', 40)))),
            crucero_cm_s=float(max(0.1, vel_raw.get('crucero_cm_s', 30.0))),
            evasion_cm_s=float(max(0.1, vel_raw.get('evasion_cm_s', 20.0)))
        )

        # 2. Ángulos Servo
        ang_raw = self.config.get('angulos_servo', {})
        self.angulos_servo = AngulosServoConfig(
            recto=int(max(40, min(140, ang_raw.get('recto', 90)))),
            giro_derecha=int(max(40, min(140, ang_raw.get('giro_derecha', 50)))),
            giro_izquierda=int(max(40, min(140, ang_raw.get('giro_izquierda', 130))))
        )

        # 3. Rangos HSV
        hsv_rojo_raw = self.config.get('hsv_rojo', {})
        self.hsv_rojo = HSVColorConfig(**self._validate_hsv(hsv_rojo_raw, [0, 120, 70], [10, 255, 255], has_two_ranges=True))
        
        hsv_verde_raw = self.config.get('hsv_verde', {})
        self.hsv_verde = HSVColorConfig(**self._validate_hsv(hsv_verde_raw, [40, 40, 40], [80, 255, 255]))
        
        hsv_magenta_raw = self.config.get('hsv_magenta', {})
        self.hsv_magenta = HSVColorConfig(**self._validate_hsv(hsv_magenta_raw, [140, 50, 50], [170, 255, 255]))

        # 4. Competición
        comp_raw = self.config.get('competicion', {})
        self.competicion = CompeticionConfig(
            modo_reto=str(comp_raw.get('modo_reto', 'obstaculos')),
            sentido_giro=str(comp_raw.get('sentido_giro', 'horario')),
            max_vueltas=int(max(1, comp_raw.get('max_vueltas', 3))),
            perimetro_pista_cm=float(max(1.0, comp_raw.get('perimetro_pista_cm', 1200.0))),
            tiempo_limite_segundos=float(max(1.0, comp_raw.get('tiempo_limite_segundos', 180.0))),
            distancia_seccion_arranque_cm=float(max(0.0, comp_raw.get('distancia_seccion_arranque_cm', 300.0))),
            retorno_arranque_habilitado=bool(comp_raw.get('retorno_arranque_habilitado', True)),
            distancia_seccion_meta_cm=float(max(0.0, comp_raw.get('distancia_seccion_meta_cm', 300.0))),
            deteccion_violacion_senales=bool(comp_raw.get('deteccion_violacion_senales', True))
        )

        # 5. Hardware
        hw_raw = self.config.get('hardware', {})
        self.hardware = HardwareConfig(
            pin_boton_inicio=int(max(1, min(40, hw_raw.get('pin_boton_inicio', 17))))
        )

        # 6. Vision
        vis_raw = self.config.get('vision', {})
        pid_raw = vis_raw.get('pid', {})
        self.vision = VisionConfig(
            min_area=float(max(1.0, vis_raw.get('min_area', 500.0))),
            width=int(max(160, min(1920, vis_raw.get('width', 640)))),
            height=int(max(120, min(1080, vis_raw.get('height', 480)))),
            format=str(vis_raw.get('format', 'RGB888')),
            factor_px_cm=float(max(0.001, vis_raw.get('factor_px_cm', 0.5))),
            odometria_visual_habilitada=bool(vis_raw.get('odometria_visual_habilitada', True)),
            pid=PIDConfig(
                kp=float(pid_raw.get('kp', 1.2)),
                ki=float(pid_raw.get('ki', 0.3)),
                kd=float(pid_raw.get('kd', 0.05)),
                integral_max=float(max(0.1, pid_raw.get('integral_max', 50.0)))
            )
        )

        # 8. LiDAR
        lid_raw = self.config.get('lidar', {})
        self.lidar = LidarConfig(
            pin_servo=int(max(1, min(40, lid_raw.get('pin_servo', 18)))),
            distancia_giro_cm=float(max(1.0, lid_raw.get('distancia_giro_cm', 50.0))),
            umbral_hueco_cm=float(max(1.0, lid_raw.get('umbral_hueco_cm', 40.0))),
            distancia_pared_cm=float(max(1.0, lid_raw.get('distancia_pared_cm', 30.0))),
            angulo_escaneo_inicio=int(max(0, min(180, lid_raw.get('angulo_escaneo_inicio', 45)))),
            angulo_escaneo_fin=int(max(0, min(180, lid_raw.get('angulo_escaneo_fin', 135)))),
            paso_escaneo=int(max(1, min(90, lid_raw.get('paso_escaneo', 15))))
        )

        # 9. Vehículo
        veh_raw = self.config.get('vehiculo', {})
        self.vehiculo = VehiculoConfig(
            largo_cm=float(max(10.0, min(50.0, veh_raw.get('largo_cm', 27.0)))),
            ancho_frente_cm=float(max(10.0, min(30.0, veh_raw.get('ancho_frente_cm', 15.0)))),
            ancho_atras_cm=float(max(10.0, min(30.0, veh_raw.get('ancho_atras_cm', 17.0)))),
            radio_giro_cm=float(max(5.0, min(20.0, veh_raw.get('radio_giro_cm', 8.5))))
        )

    # Métodos de compatibilidad hacia atrás (devuelven diccionarios de la clase de datos)
    def get_velocidades(self) -> dict:
        return self.velocidades.__dict__.copy()

    def get_angulos_servo(self) -> dict:
        return self.angulos_servo.__dict__.copy()

    def get_hsv_rojo(self) -> dict:
        return self.hsv_rojo.__dict__.copy()

    def get_hsv_verde(self) -> dict:
        return self.hsv_verde.__dict__.copy()

    def get_hsv_magenta(self) -> dict:
        return self.hsv_magenta.__dict__.copy()

    def get_competicion(self) -> dict:
        return self.competicion.__dict__.copy()

    def get_vehiculo(self) -> dict:
        return self.vehiculo.__dict__.copy()

    def get_hardware(self) -> dict:
        return self.hardware.__dict__.copy()

    def get_vision(self) -> dict:
        # Serializar anidado para mantener compatibilidad con dict
        res = self.vision.__dict__.copy()
        res['pid'] = self.vision.pid.__dict__.copy()
        return res

    def get_lidar(self) -> dict:
        return self.lidar.__dict__.copy()
