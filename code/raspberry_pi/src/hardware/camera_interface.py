"""
Camera Interface - Abstract base class for camera implementations
"""

from abc import ABC, abstractmethod
from typing import Optional, Tuple
import numpy as np


class CameraInterface(ABC):
    """Abstract interface for camera hardware"""
    
    @abstractmethod
    def setup(self, width: int = 640, height: int = 480, format: str = 'RGB888') -> bool:
        """
        Initialize camera with given configuration
        
        Args:
            width: Frame width
            height: Frame height
            format: Pixel format (e.g., 'RGB888', 'BGR888')
            
        Returns:
            True if successful, False otherwise
        """
        pass
    
    @abstractmethod
    def capture_frame(self) -> Optional[np.ndarray]:
        """
        Capture a single frame
        
        Returns:
            Frame as numpy array (RGB format), or None if failed
        """
        pass
    
    @abstractmethod
    def start(self) -> None:
        """Start camera streaming"""
        pass
    
    @abstractmethod
    def stop(self) -> None:
        """Stop camera and release resources"""
        pass
    
    @abstractmethod
    def is_connected(self) -> bool:
        """Check if camera is connected and ready"""
        pass
