#!/usr/bin/env python3
"""
Script simple de prueba para LiDAR TF-Luna con servo de paneo
Prueba lectura de distancia y control de servo
"""

import sys
import os
import time
import struct
import serial

sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))
from src.hardware import get_servo

def main():
    print("=== Prueba de LiDAR TF-Luna ===")
    
    # Configuración
    LIDAR_PORT = "/dev/serial0"
    LIDAR_BAUD = 115200
    SERVO_PIN = 18
    
    # Inicializar servo
    print("Inicializando servo...")
    servo = get_servo(use_mock=False)
    if not servo.setup(SERVO_PIN, frequency=50):
        print("Error: No se pudo inicializar el servo")
        return
    
    servo.set_angle(90)
    time.sleep(0.5)
    print("Servo centrado a 90°")
    
    # Conectar LiDAR
    print(f"Conectando a LiDAR en {LIDAR_PORT}...")
    ser = serial.Serial(LIDAR_PORT, LIDAR_BAUD, timeout=1)
    time.sleep(2)
    print("LiDAR conectado")
    
    def read_distance():
        """Lee distancia del TF-Luna en cm"""
        try:
            if ser.in_waiting >= 9:
                data = ser.read(ser.in_waiting)
                for i in range(len(data) - 8):
                    if data[i] == 0x59 and data[i+1] == 0x59:
                        frame = data[i:i+9]
                        if len(frame) == 9:
                            dist_cm = struct.unpack('<H', frame[2:4])[0]
                            signal = frame[1]
                            if signal > 30:
                                return dist_cm
        except:
            pass
        return -1.0
    
    print("\nPrueba de lectura continua (Ctrl+C para salir)...\n")
    
    try:
        # Prueba de lectura continua
        start_time = time.time()
        while time.time() - start_time < 5:
            dist = read_distance()
            if dist > 0:
                print(f"Distancia: {dist:.1f} cm", end='\r')
            time.sleep(0.1)
        print("\n")
        
        # Prueba de escaneo con servo
        print("Escaneando LiDAR (45° -> 135° -> 45°)...\n")
        
        for angle in [45, 60, 75, 90, 105, 120, 135, 120, 105, 90, 75, 60, 45]:
            servo.set_angle(angle)
            time.sleep(0.3)
            
            dist = read_distance()
            if dist > 0:
                print(f"Ángulo {angle}°: {dist:.1f} cm")
            else:
                print(f"Ángulo {angle}°: Sin lectura")
        
        # Centrar servo
        servo.set_angle(90)
        time.sleep(0.5)
        
    except KeyboardInterrupt:
        print("\nPrueba interrumpida")
    finally:
        servo.cleanup()
        ser.close()
        print("Recursos liberados")

if __name__ == "__main__":
    main()
