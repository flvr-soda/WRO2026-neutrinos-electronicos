"""
Implementación GPIO Simulada para Desarrollo en Windows
Simula comportamiento GPIO sin hardware real
"""

import logging
from .gpio_interface import GPIOInterface, GPIOMode, GPIODirection


class MockGPIO(GPIOInterface):
    """GPIO simulado para desarrollo/pruebas sin hardware"""
    
    def __init__(self):
        self._initialized = False
        self._mode = GPIOMode.BCM
        self._pins = {}  # Simulated pin states
        logging.info("Using MockGPIO (simulated hardware)")
        
    def setup(self, mode: GPIOMode = GPIOMode.BCM) -> None:
        """Inicializa GPIO simulado"""
        self._mode = mode
        self._initialized = True
        self._pins = {}
        logging.info(f"MockGPIO initialized in {mode.name} mode")
    
    def setup_pin(self, pin: int, direction: GPIODirection) -> None:
        """Configura un pin simulado"""
        if not self._initialized:
            return
            
        self._pins[pin] = {
            'direction': direction,
            'value': 0
        }
        logging.debug(f"MockGPIO: Pin {pin} set to {direction.name}")
    
    def output(self, pin: int, value: int) -> None:
        """Establece valor de salida para un pin simulado"""
        if not self._initialized or pin not in self._pins:
            return
            
        if self._pins[pin]['direction'] != GPIODirection.OUTPUT:
            logging.warning(f"MockGPIO: Pin {pin} is not configured as OUTPUT")
            return
            
        self._pins[pin]['value'] = value
        logging.debug(f"MockGPIO: Pin {pin} set to {value}")
    
    def input(self, pin: int) -> int:
        """Lee valor de entrada de un pin simulado"""
        if not self._initialized or pin not in self._pins:
            return 0
            
        if self._pins[pin]['direction'] != GPIODirection.INPUT:
            logging.warning(f"MockGPIO: Pin {pin} is not configured as INPUT")
            return 0
            
        return self._pins[pin]['value']
    
    def cleanup(self) -> None:
        """Limpia recursos GPIO simulado"""
        self._initialized = False
        self._pins = {}
        logging.info("MockGPIO cleaned up")
    
    def is_available(self) -> bool:
        """GPIO simulado siempre está disponible"""
        return True
