from .estrategia_base import EstrategiaBase

class EstrategiaNormal(EstrategiaBase):
    """
    Estrategia normal de navegación para el Reto con Obstáculos.
    Evita obstáculos rojos a la izquierda y verdes a la derecha.
    """
    
    def decidir_accion(self, deteccion: dict, velocidades: dict, angulos: dict, ancho_frame: int) -> tuple:
        color = deteccion.get("color", "NINGUNO")
        cx = deteccion.get("centroide_x", ancho_frame // 2)
        
        recto = angulos.get("recto", 90)
        
        if color == "ROJO":
            vel = velocidades.get("evasion", 40)
            evasion_roja = angulos.get("evasion_roja", 130)
            # Dirección proporcional: más al centro del frame, mayor giro
            factor = max(0.0, min(1.0, 1.0 - (abs(cx - (ancho_frame / 2)) / (ancho_frame / 2))))
            ang = int(recto + factor * (evasion_roja - recto))
        elif color == "VERDE":
            vel = velocidades.get("evasion", 40)
            evasion_verde = angulos.get("evasion_verde", 50)
            # Dirección proporcional
            factor = max(0.0, min(1.0, 1.0 - (abs(cx - (ancho_frame / 2)) / (ancho_frame / 2))))
            ang = int(recto + factor * (evasion_verde - recto))
        elif color == "MAGENTA":
            vel = velocidades.get("crucero", 60)
            ang = recto
        else:
            vel = velocidades.get("crucero", 60)
            ang = recto
        
        return (vel, ang)
    
    def get_nombre(self) -> str:
        return "normal"
