#!/usr/bin/env python3
"""
Script de prueba para servo de dirección a través de Arduino
Prueba envío de comandos de velocidad y ángulo
"""

import sys
import os
import time

# Agregar path para importar ConfigLoader
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))
from src.config_loader import ConfigLoader
from src.comms_arduino import ArduinoComms

# Cargar configuración
config_path = os.path.abspath(os.path.join(os.path.dirname(__file__), '..', 'config.yaml'))
config_loader = ConfigLoader(config_path)

class ServoTester:
    """Clase reutilizable para pruebas de servo de dirección"""
    
    def __init__(self, config_loader=None):
        self.config_loader = config_loader
        self.arduino = None
        
    def setup(self):
        """Inicializa comunicación con Arduino"""
        # ArduinoComms auto-detecta el primer puerto disponible
        self.arduino = ArduinoComms(baudrate=115200)
        time.sleep(2)  # Esperar estabilización
        
        if self.arduino.esta_conectado():
            print(f"Conectado a Arduino en {self.arduino.port}")
            return True
        else:
            print(f"Error: No se pudo conectar a Arduino")
            return False
        
    def enviar_comando(self, velocidad, angulo):
        """Envía comando de velocidad y ángulo al Arduino"""
        if self.arduino:
            self.arduino.enviar_comando(velocidad, angulo)
            
    def stop(self):
        """Cierra conexión con Arduino"""
        if self.arduino:
            self.arduino.enviar_comando(0, 90)  # Detener motores
            time.sleep(0.5)
            self.arduino.cerrar()
            print("Conexión Arduino cerrada")

def main():
    """Función principal de prueba de servo de dirección"""
    print("Iniciando prueba de servo de dirección...")
    
    servo_tester = ServoTester(config_loader)
    
    if not servo_tester.setup():
        print("No se pudo inicializar la conexión con Arduino. Saliendo...")
        return
    
    # Obtener ángulos de configuración
    angulos_config = config_loader.get_angulos_servo()
    velocidades_config = config_loader.get_velocidades()
    
    recto = angulos_config.get('recto', 90)
    giro_derecha = angulos_config.get('giro_derecha', 50)
    giro_izquierda = angulos_config.get('giro_izquierda', 130)
    velocidad_test = velocidades_config.get('evasion', 40)
    
    print(f"\nÁngulos de configuración:")
    print(f"  Recto: {recto}°")
    print(f"  Derecha: {giro_derecha}°")
    print(f"  Izquierda: {giro_izquierda}°")
    print(f"  Velocidad de prueba: {velocidad_test}%")
    print("\nIniciando secuencia de prueba. Presiona Ctrl+C para abortar.")
    print("-" * 60)
    
    try:
        # Secuencia de prueba
        print("\n1. Centrando servo (recto)...")
        servo_tester.enviar_comando(0, recto)
        time.sleep(1.5)
        
        print("2. Girando a la derecha...")
        servo_tester.enviar_comando(velocidad_test, giro_derecha)
        time.sleep(1.5)
        
        print("3. Centrando servo (recto)...")
        servo_tester.enviar_comando(0, recto)
        time.sleep(1.5)
        
        print("4. Girando a la izquierda...")
        servo_tester.enviar_comando(velocidad_test, giro_izquierda)
        time.sleep(1.5)
        
        print("5. Centrando servo (recto)...")
        servo_tester.enviar_comando(0, recto)
        time.sleep(1.5)
        
        print("\nSecuencia de prueba completada.")
        print("Iniciando prueba continua (barrido automático)...")
        print("Presiona Ctrl+C para detener.")
        
        # Prueba continua de barrido
        while True:
            print(f"\rRecto ({recto}°)...", end='')
            servo_tester.enviar_comando(0, recto)
            time.sleep(1)
            
            print(f"\rDerecha ({giro_derecha}°)...", end='')
            servo_tester.enviar_comando(velocidad_test, giro_derecha)
            time.sleep(1)
            
            print(f"\rRecto ({recto}°)...", end='')
            servo_tester.enviar_comando(0, recto)
            time.sleep(1)
            
            print(f"\rIzquierda ({giro_izquierda}°)...", end='')
            servo_tester.enviar_comando(velocidad_test, giro_izquierda)
            time.sleep(1)
            
    except KeyboardInterrupt:
        print("\nInterrupción por usuario")
    finally:
        servo_tester.stop()
        print("Prueba finalizada.")

if __name__ == "__main__":
    main()
