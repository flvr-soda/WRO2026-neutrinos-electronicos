"""
Interfaz de Servo - Clase base abstracta para implementaciones de motor servo
"""

from abc import ABC, abstractmethod


class ServoInterface(ABC):
    """Interfaz abstracta para control de motor servo"""
    
    @abstractmethod
    def setup(self, pin: int, frequency: int = 50) -> bool:
        """
        Inicializa servo en el pin dado
        
        Args:
            pin: Número de pin GPIO
            frequency: Frecuencia PWM en Hz (default 50 para servos)
            
        Returns:
            True si exitoso, False en caso contrario
        """
        pass
    
    @abstractmethod
    def set_angle(self, angle: float) -> None:
        """
        Establece ángulo del servo
        
        Args:
            angle: Ángulo en grados (0-180)
        """
        pass
    
    @abstractmethod
    def stop(self) -> None:
        """Detiene señal PWM del servo"""
        pass
    
    @abstractmethod
    def cleanup(self) -> None:
        """Limpia recursos del servo"""
        pass
    
    @abstractmethod
    def is_available(self) -> bool:
        """Verifica si el hardware del servo está disponible"""
        pass
