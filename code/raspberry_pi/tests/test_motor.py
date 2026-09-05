#!/usr/bin/env python3
"""
Script simple de prueba para motor vía Arduino
Prueba envío de comandos de velocidad
"""

import sys
import os
import time

sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))
from src.comms_arduino import ArduinoComms

def main():
    print("=== Prueba de Motor ===")
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
        print("1. Detenido (velocidad 0)")
        arduino.enviar_comando(0, 90)
        time.sleep(2)
        
        print("2. Avance lento (velocidad 30)")
        arduino.enviar_comando(30, 90)
        time.sleep(2)
        
        print("3. Avance medio (velocidad 50)")
        arduino.enviar_comando(50, 90)
        time.sleep(2)
        
        print("4. Avance rápido (velocidad 70)")
        arduino.enviar_comando(70, 90)
        time.sleep(2)
        
        print("5. Detenido (velocidad 0)")
        arduino.enviar_comando(0, 90)
        time.sleep(2)
        
        print("6. Reversa lenta (velocidad -30)")
        arduino.enviar_comando(-30, 90)
        time.sleep(2)
        
        print("7. Detenido (velocidad 0)")
        arduino.enviar_comando(0, 90)
        time.sleep(2)
        
        print("\nPrueba continua: barrido de velocidades")
        print("Presiona Ctrl+C para detener\n")
        
        # Prueba continua
        while True:
            for vel in [0, 30, 50, 70, 0, -30, 0]:
                print(f"\rVelocidad: {vel}%", end='')
                arduino.enviar_comando(vel, 90)
                time.sleep(1)
                
    except KeyboardInterrupt:
        print("\nPrueba interrumpida")
    finally:
        arduino.enviar_comando(0, 90)  # Detener motores
        time.sleep(0.5)
        arduino.cerrar()
        print("Recursos liberados")

if __name__ == "__main__":
    main()
