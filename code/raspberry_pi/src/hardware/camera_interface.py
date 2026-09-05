"""
Interfaz de Cámara - Clase base abstracta para implementaciones de cámara
"""

from abc import ABC, abstractmethod
from typing import Optional, Tuple
import numpy as np


class CameraInterface(ABC):
    """Interfaz abstracta para hardware de cámara"""
    
    @abstractmethod
    def setup(self, width: int = 640, height: int = 480, format: str = 'RGB888') -> bool:
        """
        Inicializa cámara con la configuración dada
        
        Args:
            width: Ancho del frame
            height: Alto del frame
            format: Formato de píxel (ej: 'RGB888', 'BGR888')
            
        Returns:
            True si exitoso, False en caso contrario
        """
        pass
    
    @abstractmethod
    def capture_frame(self) -> Optional[np.ndarray]:
        """
        Captura un solo frame
        
        Returns:
            Frame como array numpy (formato RGB), o None si falla
        """
        pass
    
    @abstractmethod
    def start(self) -> None:
        """Inicia streaming de cámara"""
        pass
    
    @abstractmethod
    def stop(self) -> None:
        """Detiene cámara y libera recursos"""
        pass
    
    @abstractmethod
    def is_connected(self) -> bool:
        """Verifica si la cámara está conectada y lista"""
        pass
