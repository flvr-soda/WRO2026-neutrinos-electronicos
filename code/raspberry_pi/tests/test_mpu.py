#!/usr/bin/env python3
"""
Script de prueba para MPU6050 a través de Arduino
Prueba lectura de telemetría: giro Z, ángulo servo, distancia ultrasonido trasero
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

class MPUTester:
    """Clase reutilizable para pruebas de MPU6050"""
    
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
        
    def leer_telemetria(self):
        """Lee telemetría del MPU6050 y ultrasonido"""
        if self.arduino:
            telemetria = self.arduino.obtener_telemetria()
            return telemetria
        return None
        
    def stop(self):
        """Cierra conexión con Arduino"""
        if self.arduino:
            self.arduino.cerrar()
            print("Conexión Arduino cerrada")

def main():
    """Función principal de prueba de MPU6050"""
    print("Iniciando prueba de MPU6050...")
    
    mpu_tester = MPUTester(config_loader)
    
    if not mpu_tester.setup():
        print("No se pudo inicializar la conexión con Arduino. Saliendo...")
        return
    
    print("Lectura continua de telemetría. Presiona Ctrl+C para salir.")
    print("-" * 60)
    
    try:
        while True:
            telemetria = mpu_tester.leer_telemetria()
            
            if telemetria:
                z_grados = telemetria.get('z', 0)
                angulo_servo = telemetria.get('angulo', 90)
                dist_trasera = telemetria.get('dist_trasera', -1.0)
                
                # Calcular vueltas completas
                vueltas = int(abs(z_grados) / 360.0)
                
                print(f"Z: {z_grados:7.1f}° | Vueltas: {vueltas} | Servo: {angulo_servo:3d}° | Ultrasonido: {dist_trasera:5.1f}cm", end='\r')
            else:
                print("Sin telemetría disponible...", end='\r')
            
            time.sleep(0.1)
            
    except KeyboardInterrupt:
        print("\nInterrupción por usuario")
    finally:
        mpu_tester.stop()
        print("Prueba finalizada.")

if __name__ == "__main__":
    main()
