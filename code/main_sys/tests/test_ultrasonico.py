#!/usr/bin/env python3
"""
Script simple de prueba para HC-SR04 vía Arduino
Lee telemetría del ultrasónico desde el Arduino
"""

import sys
import os
import time
import re

sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))
from src.comms_arduino import ArduinoComms

def main():
    print("=== Prueba de HC-SR04 ===")
    print("Conectando a Arduino...")
    
    arduino = ArduinoComms(baudrate=115200)
    time.sleep(2)
    
    if not arduino.esta_conectado():
        print("Error: No se pudo conectar al Arduino")
        return
    
    print(f"Conectado a Arduino en {arduino.port}")
    print("Leyendo distancia ultrasónica (Ctrl+C para salir)...\n")
    
    try:
        while True:
            telemetria = arduino.obtener_telemetria()
            if telemetria:
                dist = telemetria.get('dist_trasera', -1)
                if dist >= 0:
                    print(f"Distancia: {dist:.1f} cm", end='\r')
                else:
                    print("Fuera de rango", end='\r')
            time.sleep(0.1)
    except KeyboardInterrupt:
        print("\nPrueba finalizada")
    finally:
        arduino.cerrar()

if __name__ == "__main__":
    main()
