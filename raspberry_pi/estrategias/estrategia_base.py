from abc import ABC, abstractmethod

class EstrategiaBase(ABC):
    """
    Clase base abstracta para estrategias de navegación.
    Permite cambiar el comportamiento del robot sin recompilar código.
    """
    
    @abstractmethod
    def decidir_accion(self, deteccion: dict, velocidades: dict, angulos: dict, ancho_frame: int) -> tuple:
        """
        Decide la acción (velocidad, ángulo) basándose en la detección visual.
        
        Args:
            deteccion: Diccionario con {"color": str, "centroide_x": int, "area": int}
            velocidades: Diccionario de velocidades configuradas
            angulos: Diccionario de ángulos configurados
            ancho_frame: Ancho del frame de la cámara
            
        Returns:
            Tuple (velocidad: int, angulo: int)
        """
        pass
    
    @abstractmethod
    def get_nombre(self) -> str:
        """Retorna el nombre de la estrategia."""
        pass
