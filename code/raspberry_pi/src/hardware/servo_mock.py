"""
Mock Servo Implementation for Windows Development
Simulates servo behavior without actual hardware
"""

import logging
import time
from .servo_interface import ServoInterface


class MockServo(ServoInterface):
    """Mock servo for development/testing without hardware"""
    
    def __init__(self):
        self.pin = None
        self.frequency = 50
        self._initialized = False
        self._current_angle = 90
        logging.info("Using MockServo (simulated hardware)")
        
    def setup(self, pin: int, frequency: int = 50) -> bool:
        """Initialize mock servo"""
        self.pin = pin
        self.frequency = frequency
        self._initialized = True
        self._current_angle = 90
        logging.info(f"MockServo initialized on pin {pin} at {frequency}Hz")
        return True
    
    def set_angle(self, angle: float) -> None:
        """Set simulated servo angle (0-180 degrees)"""
        if not self._initialized:
            return
            
        # Clamp angle to valid range
        angle = max(0, min(180, angle))
        self._current_angle = angle
        logging.debug(f"MockServo: Angle set to {angle} degrees")
        # Simulate servo movement delay
        time.sleep(0.01)
    
    def stop(self) -> None:
        """Stop mock servo PWM signal (no-op)"""
        logging.debug("MockServo: PWM stopped")
    
    def cleanup(self) -> None:
        """Clean up mock servo resources"""
        self._initialized = False
        logging.info("MockServo cleaned up")
    
    def is_available(self) -> bool:
        """Mock servo is always available"""
        return True
