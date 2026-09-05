"""
Servo Interface - Abstract base class for servo motor implementations
"""

from abc import ABC, abstractmethod


class ServoInterface(ABC):
    """Abstract interface for servo motor control"""
    
    @abstractmethod
    def setup(self, pin: int, frequency: int = 50) -> bool:
        """
        Initialize servo on given pin
        
        Args:
            pin: GPIO pin number
            frequency: PWM frequency in Hz (default 50 for servos)
            
        Returns:
            True if successful, False otherwise
        """
        pass
    
    @abstractmethod
    def set_angle(self, angle: float) -> None:
        """
        Set servo angle
        
        Args:
            angle: Angle in degrees (0-180)
        """
        pass
    
    @abstractmethod
    def stop(self) -> None:
        """Stop servo PWM signal"""
        pass
    
    @abstractmethod
    def cleanup(self) -> None:
        """Clean up servo resources"""
        pass
    
    @abstractmethod
    def is_available(self) -> bool:
        """Check if servo hardware is available"""
        pass
