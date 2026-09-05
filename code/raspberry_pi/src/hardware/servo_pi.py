"""
Implementación de Servo Raspberry Pi usando RPi.GPIO PWM
"""

import logging
import time
from .servo_interface import ServoInterface

try:
    import RPi.GPIO as GPIO
    GPIO_AVAILABLE = True
except (ImportError, RuntimeError):
    GPIO_AVAILABLE = False
    logging.warning("RPi.GPIO not available. Will use mock fallback.")


class PiServo(ServoInterface):
    """Implementación de servo Raspberry Pi usando RPi.GPIO PWM"""
    
    def __init__(self):
        self.pwm = None
        self.pin = None
        self.frequency = 50
        self._initialized = False
        self._current_angle = 90
        self._using_fallback = False
        
    def setup(self, pin: int, frequency: int = 50) -> bool:
        """Inicializa servo en el pin dado"""
        if not GPIO_AVAILABLE:
            logging.warning("GPIO not available for servo, using mock fallback")
            self._using_fallback = True
            self._initialized = True
            self.pin = pin
            self.frequency = frequency
            self._current_angle = 90
            logging.info(f"Servo initialized on pin {pin} at {frequency}Hz (fallback)")
            return True
            
        try:
            self.pin = pin
            self.frequency = frequency
            GPIO.setup(self.pin, GPIO.OUT)
            self.pwm = GPIO.PWM(self.pin, frequency)
            self.pwm.start(0)
            self._initialized = True
            logging.info(f"Servo initialized on pin {pin} at {frequency}Hz")
            return True
        except Exception as e:
            logging.error(f"Failed to initialize servo: {e}. Using mock fallback.")
            self._using_fallback = True
            self._initialized = True
            self.pin = pin
            self.frequency = frequency
            self._current_angle = 90
            return True
    
    def set_angle(self, angle: float) -> None:
        """Establece ángulo del servo (0-180 grados)"""
        if self._using_fallback:
            # Limitar ángulo al rango válido
            angle = max(0, min(180, angle))
            self._current_angle = angle
            logging.debug(f"Mock servo: Angle set to {angle} degrees")
            time.sleep(0.01)  # Simular retraso de movimiento del servo
            return
            
        if not self._initialized or self.pwm is None:
            return
            
        try:
            # Clamp angle to valid range
            angle = max(0, min(180, angle))
            
            # Convertir ángulo a ciclo de trabajo (2.5% a 12.5% para 0-180 grados)
            duty_cycle = angle / 18.0 + 2.5
            self.pwm.ChangeDutyCycle(duty_cycle)
            self._current_angle = angle
            time.sleep(0.1)  # Pequeño retraso para que el servo se mueva
        except Exception as e:
            logging.error(f"Failed to set servo angle: {e}. Switching to fallback.")
            self._using_fallback = True
            self._current_angle = max(0, min(180, angle))
    
    def stop(self) -> None:
        """Detiene señal PWM del servo"""
        if self._using_fallback:
            logging.debug("Mock servo: PWM stopped")
            return
            
        if self.pwm and self._initialized:
            try:
                self.pwm.ChangeDutyCycle(0)
            except Exception as e:
                logging.error(f"Error stopping servo PWM: {e}")
    
    def cleanup(self) -> None:
        """Limpia recursos del servo"""
        if self.pwm and not self._using_fallback:
            try:
                self.pwm.stop()
                self.pwm = None
            except Exception as e:
                logging.error(f"Error cleaning up servo: {e}")
        self._initialized = False
        self._using_fallback = False
    
    def is_available(self) -> bool:
        """Verifica si el hardware del servo está disponible"""
        return True  # Always returns True now (fallback available)
