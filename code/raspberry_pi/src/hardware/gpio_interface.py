"""
GPIO Interface - Abstract base class for GPIO implementations
"""

from abc import ABC, abstractmethod
from enum import IntEnum


class GPIOMode(IntEnum):
    """GPIO numbering modes"""
    BCM = 0
    BOARD = 1


class GPIODirection(IntEnum):
    """GPIO pin directions"""
    INPUT = 0
    OUTPUT = 1


class GPIOInterface(ABC):
    """Abstract interface for GPIO hardware"""
    
    @abstractmethod
    def setup(self, mode: GPIOMode = GPIOMode.BCM) -> None:
        """
        Initialize GPIO with given numbering mode
        
        Args:
            mode: GPIO numbering mode (BCM or BOARD)
        """
        pass
    
    @abstractmethod
    def setup_pin(self, pin: int, direction: GPIODirection) -> None:
        """
        Configure a specific pin
        
        Args:
            pin: Pin number
            direction: INPUT or OUTPUT
        """
        pass
    
    @abstractmethod
    def output(self, pin: int, value: int) -> None:
        """
        Set output value for a pin
        
        Args:
            pin: Pin number
            value: 0 (LOW) or 1 (HIGH)
        """
        pass
    
    @abstractmethod
    def input(self, pin: int) -> int:
        """
        Read input value from a pin
        
        Args:
            pin: Pin number
            
        Returns:
            0 (LOW) or 1 (HIGH)
        """
        pass
    
    @abstractmethod
    def cleanup(self) -> None:
        """Clean up GPIO resources"""
        pass
    
    @abstractmethod
    def is_available(self) -> bool:
        """Check if GPIO hardware is available"""
        pass
