"""
Implementación de Servo Simulado para Desarrollo en Windows
Simula comportamiento de servo sin hardware real
"""

import logging
import time
from .servo_interface import ServoInterface


class MockServo(ServoInterface):
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
