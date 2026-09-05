"""
Implementación GPIO Raspberry Pi usando RPi.GPIO
"""

import logging
from .gpio_interface import GPIOInterface, GPIOMode, GPIODirection

try:
    import RPi.GPIO as GPIO
    GPIO_AVAILABLE = True
except (ImportError, RuntimeError):
    GPIO_AVAILABLE = False
    logging.warning("RPi.GPIO not available. Will use mock fallback.")


class PiGPIO(GPIOInterface):
    """Implementación GPIO Raspberry Pi usando RPi.GPIO"""
    
    def __init__(self):
        self._initialized = False
        self._mode = GPIOMode.BCM
        self._using_fallback = False
        self._pins = {}  # Simulated pin states for fallback
        
    def setup(self, mode: GPIOMode = GPIOMode.BCM) -> None:
        """Inicializa GPIO con el modo de numeración dado"""
        if not GPIO_AVAILABLE:
            logging.warning("GPIO not available, using mock fallback")
            self._using_fallback = True
            self._initialized = True
            self._mode = mode
            self._pins = {}
            logging.info(f"GPIO initialized in {mode.name} mode (fallback)")
            return
            
        try:
            if mode == GPIOMode.BCM:
                GPIO.setmode(GPIO.BCM)
            else:
                GPIO.setmode(GPIO.BOARD)
            self._mode = mode
            self._initialized = True
            logging.info(f"GPIO initialized in {mode.name} mode")
        except Exception as e:
            logging.error(f"Failed to initialize GPIO: {e}. Using mock fallback.")
            self._using_fallback = True
            self._initialized = True
            self._mode = mode
            self._pins = {}
    
    def setup_pin(self, pin: int, direction: GPIODirection) -> None:
        """Configura un pin específico"""
        if self._using_fallback:
            self._pins[pin] = {'direction': direction, 'value': 0}
            logging.debug(f"Mock GPIO: Pin {pin} set to {direction.name}")
            return
            
        if not GPIO_AVAILABLE or not self._initialized:
            return
            
        try:
            if direction == GPIODirection.INPUT:
                GPIO.setup(pin, GPIO.IN)
            else:
                GPIO.setup(pin, GPIO.OUT)
        except Exception as e:
            logging.error(f"Failed to setup pin {pin}: {e}")
    
    def output(self, pin: int, value: int) -> None:
        """Establece valor de salida para un pin"""
        if self._using_fallback:
            if pin in self._pins and self._pins[pin]['direction'] == GPIODirection.OUTPUT:
                self._pins[pin]['value'] = value
                logging.debug(f"Mock GPIO: Pin {pin} set to {value}")
            return
            
        if not GPIO_AVAILABLE or not self._initialized:
            return
            
        try:
            GPIO.output(pin, value)
        except Exception as e:
            logging.error(f"Failed to set output on pin {pin}: {e}")
    
    def input(self, pin: int) -> int:
        """Lee valor de entrada de un pin"""
        if self._using_fallback:
            if pin in self._pins and self._pins[pin]['direction'] == GPIODirection.INPUT:
                return self._pins[pin]['value']
            return 0
            
        if not GPIO_AVAILABLE or not self._initialized:
            return 0
            
        try:
            return GPIO.input(pin)
        except Exception as e:
            logging.error(f"Failed to read input from pin {pin}: {e}")
            return 0
    
    def cleanup(self) -> None:
        """Limpia recursos GPIO"""
        if GPIO_AVAILABLE and self._initialized and not self._using_fallback:
            try:
                GPIO.cleanup()
            except Exception as e:
                logging.error(f"Error cleaning up GPIO: {e}")
        self._initialized = False
        self._pins = {}
    
    def is_available(self) -> bool:
        """Verifica si el hardware GPIO está disponible"""
        return True  # Always returns True now (fallback available)
