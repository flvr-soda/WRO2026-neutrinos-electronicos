"""
Interfaz GPIO - Clase base abstracta para implementaciones GPIO
"""

from abc import ABC, abstractmethod
from enum import IntEnum


class GPIOMode(IntEnum):
    """Modos de numeración GPIO"""
    BCM = 0
    BOARD = 1


class GPIODirection(IntEnum):
    """Direcciones de pines GPIO"""
    INPUT = 0
    OUTPUT = 1


class GPIOInterface(ABC):
    """Interfaz abstracta para hardware GPIO"""
    
    @abstractmethod
    def setup(self, mode: GPIOMode = GPIOMode.BCM) -> None:
        """
        Inicializa GPIO con el modo de numeración dado
        
        Args:
            mode: Modo de numeración GPIO (BCM o BOARD)
        """
        pass
    
    @abstractmethod
    def setup_pin(self, pin: int, direction: GPIODirection) -> None:
        """
        Configura un pin específico
        
        Args:
            pin: Número de pin
            direction: INPUT o OUTPUT
        """
        pass
    
    @abstractmethod
    def output(self, pin: int, value: int) -> None:
        """
        Establece valor de salida para un pin
        
        Args:
            pin: Número de pin
            value: 0 (LOW) o 1 (HIGH)
        """
        pass
    
    @abstractmethod
    def input(self, pin: int) -> int:
        """
        Lee valor de entrada de un pin
        
        Args:
            pin: Número de pin
            
        Returns:
            0 (LOW) o 1 (HIGH)
        """
        pass
    
    @abstractmethod
    def cleanup(self) -> None:
        """Limpia recursos GPIO"""
        pass
    
    @abstractmethod
    def is_available(self) -> bool:
        """Verifica si el hardware GPIO está disponible"""
        pass
