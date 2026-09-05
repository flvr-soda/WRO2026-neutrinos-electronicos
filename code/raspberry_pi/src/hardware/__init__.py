"""
Hardware Abstraction Layer
Provides interfaces for hardware components with mock implementations for development.
"""

from .camera_interface import CameraInterface
from .gpio_interface import GPIOInterface, GPIOMode, GPIODirection
from .servo_interface import ServoInterface

# Raspberry Pi implementations
from .camera_pi import PiCamera
from .gpio_pi import PiGPIO
from .servo_pi import PiServo

# Mock implementations for development
from .camera_mock import MockCamera
from .gpio_mock import MockGPIO
from .servo_mock import MockServo

__all__ = [
    'CameraInterface', 'GPIOInterface', 'ServoInterface',
    'GPIOMode', 'GPIODirection',
    'PiCamera', 'PiGPIO', 'PiServo',
    'MockCamera', 'MockGPIO', 'MockServo'
]


def get_camera(use_mock: bool = False) -> CameraInterface:
    """
    Factory function to get appropriate camera implementation
    
    Pi implementations now have automatic fallback built-in, so they work
    even when hardware/libraries are unavailable.
    
    Args:
        use_mock: If True, explicitly use mock implementation; otherwise use Pi implementation
        
    Returns:
        CameraInterface instance
    """
    if use_mock:
        return MockCamera()
    else:
        return PiCamera()  # Has automatic fallback


def get_gpio(use_mock: bool = False) -> GPIOInterface:
    """
    Factory function to get appropriate GPIO implementation
    
    Pi implementations now have automatic fallback built-in, so they work
    even when hardware/libraries are unavailable.
    
    Args:
        use_mock: If True, explicitly use mock implementation; otherwise use Pi implementation
        
    Returns:
        GPIOInterface instance
    """
    if use_mock:
        return MockGPIO()
    else:
        return PiGPIO()  # Has automatic fallback


def get_servo(use_mock: bool = False) -> ServoInterface:
    """
    Factory function to get appropriate servo implementation
    
    Pi implementations now have automatic fallback built-in, so they work
    even when hardware/libraries are unavailable.
    
    Args:
        use_mock: If True, explicitly use mock implementation; otherwise use Pi implementation
        
    Returns:
        ServoInterface instance
    """
    if use_mock:
        return MockServo()
    else:
        return PiServo()  # Has automatic fallback
