#!/usr/bin/env python3
"""
Script simple de prueba para servo de dirección vía Arduino
Prueba envío de comandos de ángulo
"""

import sys
import os
import time

sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))
from src.comms_arduino import ArduinoComms

def main():
    print("=== Prueba de Servo de Dirección ===")
    print("Conectando a Arduino...")
    
    arduino = ArduinoComms(baudrate=115200)
    time.sleep(2)
    
    if not arduino.esta_conectado():
        print("Error: No se pudo conectar al Arduino")
        return
    
    print(f"Conectado a Arduino en {arduino.port}")
    print("Iniciando secuencia de prueba (Ctrl+C para salir)...\n")
    
    try:
        # Secuencia de prueba
        print("1. Centrado (90°)")
        arduino.enviar_comando(0, 90)
        time.sleep(2)
        
        print("2. Derecha (50°)")
        arduino.enviar_comando(0, 50)
        time.sleep(2)
        
        print("3. Centrado (90°)")
        arduino.enviar_comando(0, 90)
        time.sleep(2)
        
        print("4. Izquierda (130°)")
        arduino.enviar_comando(0, 130)
        time.sleep(2)
        
        print("5. Centrado (90°)")
        arduino.enviar_comando(0, 90)
        time.sleep(2)
        
        print("\nPrueba continua: barrido de ángulos")
        print("Presiona Ctrl+C para detener\n")
        
        # Prueba continua
        while True:
            for angle in [90, 50, 90, 130, 90]:
                print(f"\rÁngulo: {angle}°", end='')
                arduino.enviar_comando(0, angle)
                time.sleep(1)
                
    except KeyboardInterrupt:
        print("\nPrueba interrumpida")
    finally:
        arduino.enviar_comando(0, 90)  # Centrar servo
        time.sleep(0.5)
        arduino.cerrar()
        print("Recursos liberados")

if __name__ == "__main__":
    main()
