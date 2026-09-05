"""
Implementación de Cámara Raspberry Pi usando Picamera2
"""

import numpy as np
import logging
from typing import Optional
from .camera_interface import CameraInterface

try:
    from picamera2 import Picamera2
    PICAMERA_AVAILABLE = True
except ImportError:
    PICAMERA_AVAILABLE = False
    logging.warning("picamera2 not available. Will use mock fallback.")


class PiCamera(CameraInterface):
    """Implementación de cámara Raspberry Pi usando Picamera2"""
    
    def __init__(self):
        self.picam2 = None
        self.config = None
        self._connected = False
        self._using_fallback = False
        
    def setup(self, width: int = 640, height: int = 480, format: str = 'RGB888') -> bool:
        """Inicializa cámara con la configuración dada"""
        if not PICAMERA_AVAILABLE:
            logging.warning("picamera2 not available, using mock fallback")
            self._using_fallback = True
            return self._setup_fallback(width, height, format)
            
        try:
            self.picam2 = Picamera2()
            self.config = self.picam2.create_video_configuration(
                main={"format": format, "size": (width, height)}
            )
            self.picam2.configure(self.config)
            self._connected = True
            logging.info(f"Camera initialized: {width}x{height}, format={format}")
            return True
        except Exception as e:
            logging.error(f"Failed to initialize camera: {e}. Using mock fallback.")
            self._using_fallback = True
            return self._setup_fallback(width, height, format)
    
    def _setup_fallback(self, width: int, height: int, format: str) -> bool:
        """Configura fallback simulado cuando la cámara real falla"""
        self.width = width
        self.height = height
        self._connected = True
        self._frame_count = 0
        logging.info(f"Using mock camera fallback: {width}x{height}")
        return True
    
    def capture_frame(self) -> Optional[np.ndarray]:
        """Captura un solo frame en formato RGB"""
        if self._using_fallback:
            return self._capture_fallback_frame()
            
        if not self._connected or self.picam2 is None:
            return None
            
        try:
            frame = self.picam2.capture_array()
            return frame  # Already in RGB format from Picamera2
        except Exception as e:
            logging.error(f"Failed to capture frame: {e}. Switching to fallback.")
            self._using_fallback = True
            return self._capture_fallback_frame()
    
    def _capture_fallback_frame(self) -> Optional[np.ndarray]:
        """Captura un frame simulado (patrón de gradiente)"""
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
        """Inicia streaming de cámara"""
        if self._using_fallback:
            self._connected = True
            return
            
        if self.picam2 and not self._connected:
            try:
                self.picam2.start()
                self._connected = True
            except Exception as e:
                logging.error(f"Failed to start camera: {e}. Switching to fallback.")
                self._using_fallback = True
                self._connected = True
    
    def stop(self) -> None:
        """Detiene cámara y libera recursos"""
        if self.picam2:
            try:
                if self._connected and not self._using_fallback:
                    self.picam2.stop()
                self.picam2.close()
            except Exception as e:
                logging.error(f"Error stopping camera: {e}")
            finally:
                self.picam2 = None
                self._connected = False
        self._using_fallback = False
    
    def is_connected(self) -> bool:
        """Verifica si la cámara está conectada y lista"""
        return self._connected
