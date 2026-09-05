"""
Capa de Abstracción de Hardware
Proporciona interfaces para componentes de hardware con implementaciones simuladas para desarrollo.
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
    Función fábrica para obtener la implementación de cámara apropiada
    
    Las implementaciones Pi ahora tienen fallback automático integrado, así que funcionan
    incluso cuando el hardware/bibliotecas no están disponibles.
    
    Args:
        use_mock: Si True, usa explícitamente implementación simulada; de lo contrario usa implementación Pi
        
    Returns:
        Instancia de CameraInterface
    """
    if use_mock:
        return MockCamera()
    else:
        return PiCamera()  # Has automatic fallback


def get_gpio(use_mock: bool = False) -> GPIOInterface:
    """
    Función fábrica para obtener la implementación GPIO apropiada
    
    Las implementaciones Pi ahora tienen fallback automático integrado, así que funcionan
    incluso cuando el hardware/bibliotecas no están disponibles.
    
    Args:
        use_mock: Si True, usa explícitamente implementación simulada; de lo contrario usa implementación Pi
        
    Returns:
        Instancia de GPIOInterface
    """
    if use_mock:
        return MockGPIO()
    else:
        return PiGPIO()  # Has automatic fallback


def get_servo(use_mock: bool = False) -> ServoInterface:
    """
    Función fábrica para obtener la implementación de servo apropiada
    
    Las implementaciones Pi ahora tienen fallback automático integrado, así que funcionan
    incluso cuando el hardware/bibliotecas no están disponibles.
    
    Args:
        use_mock: Si True, usa explícitamente implementación simulada; de lo contrario usa implementación Pi
        
    Returns:
        Instancia de ServoInterface
    """
    if use_mock:
        return MockServo()
    else:
        return PiServo()  # Has automatic fallback
