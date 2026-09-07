#!/usr/bin/env python3
"""
Script simple de prueba para MPU6050 vía Arduino
Lee telemetría: giro Z, ángulo servo, distancia ultrasonido trasero
"""

import sys
import os
import time

sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))
from src.comms_arduino import ArduinoComms

def main():
    print("=== Prueba de MPU6050 ===")
    print("Conectando a Arduino...")
    
    arduino = ArduinoComms(baudrate=115200)
    time.sleep(2)
    
    if not arduino.esta_conectado():
        print("Error: No se pudo conectar al Arduino")
        return
    
    print(f"Conectado a Arduino en {arduino.port}")
    print("Leyendo giroscopio (Ctrl+C para salir)...\n")
    
    try:
        while True:
            telemetria = arduino.obtener_telemetria()
            if telemetria:
                z_grados = telemetria.get('z', 0)
                angulo_servo = telemetria.get('angulo', 90)
                dist_trasera = telemetria.get('dist_trasera', -1)
                
                vueltas = int(abs(z_grados) / 360.0)
                
                print(f"Z: {z_grados:7.1f}° | Vueltas: {vueltas} | Servo: {angulo_servo:3d}° | Ultrasonido: {dist_trasera:5.1f}cm", end='\r')
            time.sleep(0.1)
    except KeyboardInterrupt:
        print("\nPrueba finalizada")
    finally:
        arduino.cerrar()

if __name__ == "__main__":
    main()
