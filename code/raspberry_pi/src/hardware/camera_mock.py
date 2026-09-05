"""
Mock Camera Implementation for Windows Development
Simulates camera behavior without actual hardware
"""

import numpy as np
import logging
from typing import Optional
from .camera_interface import CameraInterface


class MockCamera(CameraInterface):
    """Mock camera for development/testing without hardware"""
    
    def __init__(self):
        self.width = 640
        self.height = 480
        self._connected = False
        self._frame_count = 0
        logging.info("Using MockCamera (simulated hardware)")
        
    def setup(self, width: int = 640, height: int = 480, format: str = 'RGB888') -> bool:
        """Initialize mock camera"""
        self.width = width
        self.height = height
        self._connected = True
        logging.info(f"MockCamera initialized: {width}x{height}, format={format}")
        return True
    
    def capture_frame(self) -> Optional[np.ndarray]:
        """Capture a simulated frame (gradient pattern)"""
        if not self._connected:
            return None
            
        self._frame_count += 1
        
        # Create a gradient pattern that changes over time
        frame = np.zeros((self.height, self.width, 3), dtype=np.uint8)
        
        # Create a color gradient that shifts over time
        offset = (self._frame_count * 2) % 256
        for y in range(self.height):
            for x in range(self.width):
                frame[y, x, 0] = (x + offset) % 256  # Red
                frame[y, x, 1] = (y + offset) % 256  # Green
                frame[y, x, 2] = ((x + y) // 2 + offset) % 256  # Blue
        
        return frame
    
    def start(self) -> None:
        """Start mock camera (no-op)"""
        self._connected = True
        logging.info("MockCamera started")
    
    def stop(self) -> None:
        """Stop mock camera"""
        self._connected = False
        logging.info("MockCamera stopped")
    
    def is_connected(self) -> bool:
        """Check if mock camera is connected"""
        return self._connected
