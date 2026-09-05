"""
Implementación de Cámara Simulada para Desarrollo en Windows
Simula comportamiento de cámara sin hardware real
"""

import numpy as np
import logging
from typing import Optional
from .camera_interface import CameraInterface


class MockCamera(CameraInterface):
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
