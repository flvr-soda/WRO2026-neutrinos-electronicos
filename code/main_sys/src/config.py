"""
Configuración del Sistema Principal - Variables directas
Todas las configuraciones están declaradas directamente sin archivo YAML externo
"""

# ==================== VELOCIDADES ====================
VELOCIDADES = {
    "crucero": 60,
    "evasion": 40,
    "crucero_cm_s": 40.0,   # Velocidad objetivo en cm/s para el PID (recta)
    "evasion_cm_s": 30.0    # Velocidad objetivo en cm/s para el PID (evasión/giro)
}

# ==================== ÁNGULOS SERVO ====================
ANGULOS_SERVO = {
    "recto": 135,           # Centro del rango 0-270°
    "giro_derecha": 0,      # Ángulo de servo para girar a la DERECHA (Regla 9.19: ROJO se mantiene a la derecha) - Extremo derecho
    "giro_izquierda": 270   # Ángulo de servo para girar a la IZQUIERDA (Regla 9.19: VERDE se mantiene a la izquierda) - Extremo izquierdo
}

# ==================== RANGOS HSV PARA DETECCIÓN DE COLORES ====================
HSV_ROJO = {
    "lower": [0, 120, 70],
    "upper": [10, 255, 255],
    "lower2": [170, 120, 70],
    "upper2": [180, 255, 255]
}

HSV_VERDE = {
    "lower": [40, 40, 40],
    "upper": [80, 255, 255]
}

HSV_MAGENTA = {
    "lower": [140, 50, 50],
    "upper": [170, 255, 255]
}

# ==================== CONFIGURACIÓN DE COMPETICIÓN ====================
COMPETICION = {
    "modo_reto": "abierto",       # "abierto" o "obstaculos"
    "sentido_giro": "horario",    # "horario" o "antihorario"
    "max_vueltas": 3,
    "perimetro_pista_cm": 1200,  # Perímetro aproximado del circuito en cm
    "tiempo_limite_segundos": 180,  # Límite de tiempo de 3 minutos (180 segundos) según regla 9.25.1
    "distancia_seccion_arranque_cm": 300,  # Distancia desde inicio hasta sección de arranque (Regla 9.22)
    "retorno_arranque_habilitado": True,  # Habilitar retorno a sección de arranque después de 3 vueltas
    "distancia_seccion_meta_cm": 300,     # Distancia desde inicio hasta sección de meta (Regla 9.25.2, Reto Abierto)
    "deteccion_violacion_senales": True,   # Habilitar detección de violación de señales (Regla 9.25.5)
    # ==================== AUTO-DETECCIÓN ====================
    "auto_detect_modo": True,           # Habilitar auto-detección del modo de competición
    "modo_deteccion_timeout_seg": 10,   # Ventana de tiempo para detección de modo (segundos)
    "modo_deteccion_umbral_colores": 5, # Mínimo de detecciones de color para activar modo obstáculos
    "modo_reto_default": "abierto",     # Modo por defecto si falla la detección
    "auto_detect_sentido": True,         # Habilitar auto-detección del sentido de giro
    "sentido_deteccion_distancia_cm": 70, # Umbral de distancia para detección de esquina (cm)
    "sentido_deteccion_timeout_seg": 15,  # Ventana de tiempo para detección de sentido (segundos)
    "sentido_giro_default": "horario"    # Sentido por defecto si falla la detección
}

# ==================== CONFIGURACIÓN DE HARDWARE ====================
HARDWARE = {
    "pin_boton_inicio": 17  # GPIO pin para botón de inicio físico (Regla 9.11) - Physical Pin 11
}

# ==================== CONFIGURACIÓN DE VISIÓN ====================
VISION = {
    "min_area": 500,
    "camera_index": 0,        # Índice de cámara USB (0 para /dev/video0)
    "width": 640,             # Ancho de frame para cámara USB
    "height": 480,            # Alto de frame para cámara USB
    "factor_px_cm": 0.5,      # Factor de calibración: 1 píxel = X cm en el suelo
    "odometria_visual_habilitada": True,  # true para regular velocidad con PID y odometría visual
    "pid": {
        "kp": 1.2,            # Ganancia proporcional
        "ki": 0.3,            # Ganancia integral
        "kd": 0.05,           # Ganancia derivativa
        "integral_max": 50.0  # Límite del acumulador integral (anti-windup)
    }
}

# ==================== CONFIGURACIÓN DE LIDAR ====================
LIDAR = {
    "pin_servo": 18,
    "distancia_giro_cm": 70.0,
    "umbral_hueco_cm": 55,       # Distancia mínima para considerar un hueco válido
    "distancia_pared_cm": 40.0,  # Distancia objetivo a la pared al estacionar
    "angulo_escaneo_inicio": 45,
    "angulo_escaneo_fin": 135,
    "paso_escaneo": 15
}

# ==================== CONFIGURACIÓN DE VEHÍCULO ====================
VEHICULO = {
    "largo_cm": 27.0,          # Longitud total del vehículo
    "ancho_frente_cm": 15.0,    # Ancho del eje delantero
    "ancho_atras_cm": 17.0,     # Ancho del eje trasero
    "radio_giro_cm": 8.5        # Radio de giro aproximado (mitad del ancho máximo)
}

# ==================== PUERTOS SERIALES ====================
SERIAL_PORTS = {
    "arduino": "/dev/ttyUSB0",  # Puerto serial para Arduino
    "lidar": "/dev/serial0"     # Puerto serial para LiDAR TF-Luna
}

# ==================== CONTROLADOR PID ====================
class PID:
    """Controlador PID genérico con anti-windup."""
    def __init__(self, kp, ki, kd, output_min=0, output_max=100, integral_max=50.0):
        self.kp = kp
        self.ki = ki
        self.kd = kd
        self.output_min = output_min
        self.output_max = output_max
        self.integral_max = integral_max
        
        self.integral = 0.0
        self.prev_error = 0.0
        self.first_iteration = True
        
    def set_setpoint(self, setpoint):
        """Establece el valor objetivo."""
        self.setpoint = setpoint
        
    def compute(self, measurement):
        """Calcula la salida del PID basada en la medición actual."""
        error = self.setpoint - measurement
        
        # En la primera iteración, retornar 0 para evitar picos
        if self.first_iteration:
            self.first_iteration = False
            self.prev_error = error
            return 0.0
        
        # Término proporcional
        p_term = self.kp * error
        
        # Término integral con anti-windup
        self.integral += error
        if self.integral > self.integral_max:
            self.integral = self.integral_max
        elif self.integral < -self.integral_max:
            self.integral = -self.integral_max
        i_term = self.ki * self.integral
        
        # Término derivativo
        d_term = self.kd * (error - self.prev_error)
        self.prev_error = error
        
        # Calcular salida
        output = p_term + i_term + d_term
        
        # Limitar salida al rango permitido
        output = max(self.output_min, min(self.output_max, output))
        
        return output

# ==================== FUNCIONES DE COMPATIBILIDAD ====================
def get_velocidades():
    return VELOCIDADES.copy()

def get_angulos_servo():
    return ANGULOS_SERVO.copy()

def get_hsv_rojo():
    return HSV_ROJO.copy()

def get_hsv_verde():
    return HSV_VERDE.copy()

def get_hsv_magenta():
    return HSV_MAGENTA.copy()

def get_competicion():
    return COMPETICION.copy()

def get_vehiculo():
    return VEHICULO.copy()

def get_hardware():
    return HARDWARE.copy()

def get_vision():
    return VISION.copy()

def get_lidar():
    return LIDAR.copy()

def get_serial_ports():
    return SERIAL_PORTS.copy()
