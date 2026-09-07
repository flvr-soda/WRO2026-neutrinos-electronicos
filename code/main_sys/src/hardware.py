"""
Hardware Abstraction Layer for Testing
Simplified implementations for development/testing without real hardware
"""

import numpy as np
import logging
import time
from typing import Optional


class MockCamera:
    """Cámara simulada para desarrollo/pruebas sin hardware"""
    
    def __init__(self):
        self.width = 640
        self.height = 480
        self._connected = False
        self._frame_count = 0
        logging.info("Using MockCamera (simulated hardware)")
        
    def setup(self, width: int = 640, height: int = 480, format: str = 'RGB888') -> bool:
        """Inicializa cámara simulada"""
        self.width = width
        self.height = height
        self._connected = True
        logging.info(f"MockCamera initialized: {width}x{height}, format={format}")
        return True
    
    def capture_frame(self) -> Optional[np.ndarray]:
        """Captura un frame simulado (patrón de gradiente)"""
        if not self._connected:
            return None
            
        self._frame_count += 1
        
        # Crear un patrón de gradiente que cambia con el tiempo
        frame = np.zeros((self.height, self.width, 3), dtype=np.uint8)
        
        # Crear un gradiente de color que cambia con el tiempo
        offset = (self._frame_count * 2) % 256
        for y in range(self.height):
            for x in range(self.width):
                frame[y, x, 0] = (x + offset) % 256  # Red
                frame[y, x, 1] = (y + offset) % 256  # Green
                frame[y, x, 2] = ((x + y) // 2 + offset) % 256  # Blue
        
        return frame
    
    def start(self) -> None:
        """Inicia cámara simulada (sin operación)"""
        self._connected = True
        logging.info("MockCamera started")
    
    def stop(self) -> None:
        """Detiene cámara simulada"""
        self._connected = False
        logging.info("MockCamera stopped")
    
    def is_connected(self) -> bool:
        """Verifica si la cámara simulada está conectada"""
        return self._connected


class MockServo:
    """Servo simulado para desarrollo/pruebas sin hardware"""
    
    def __init__(self):
        self.pin = None
        self.frequency = 50
        self._initialized = False
        self._current_angle = 90
        logging.info("Using MockServo (simulated hardware)")
        
    def setup(self, pin: int, frequency: int = 50) -> bool:
        """Inicializa servo simulado"""
        self.pin = pin
        self.frequency = frequency
        self._initialized = True
        self._current_angle = 90
        logging.info(f"MockServo initialized on pin {pin} at {frequency}Hz")
        return True
    
    def set_angle(self, angle: float) -> None:
        """Establece ángulo simulado del servo (0-180 grados)"""
        if not self._initialized:
            return
            
        # Limitar ángulo al rango válido
        angle = max(0, min(180, angle))
        self._current_angle = angle
        logging.debug(f"MockServo: Angle set to {angle} degrees")
        # Simular retraso de movimiento del servo
        time.sleep(0.01)
    
    def stop(self) -> None:
        """Detiene señal PWM del servo simulado (sin operación)"""
        logging.debug("MockServo: PWM stopped")
    
    def cleanup(self) -> None:
        """Limpia recursos del servo simulado"""
        self._initialized = False
        logging.info("MockServo cleaned up")
    
    def is_available(self) -> bool:
        """Servo simulado siempre está disponible"""
        return True


def get_camera(use_mock: bool = False) -> MockCamera:
    """
    Función fábrica para obtener implementación de cámara
    
    Args:
        use_mock: Si True, usa implementación simulada
        
    Returns:
        Instancia de MockCamera
    """
    return MockCamera()


def get_servo(use_mock: bool = False) -> MockServo:
    """
    Función fábrica para obtener implementación de servo
    
    Args:
        use_mock: Si True, usa implementación simulada
        
    Returns:
        Instancia de MockServo
    """
    return MockServo()
