#!/usr/bin/env python3
"""
Script simple de prueba para cámara CSI
Prueba captura de frames y detección de colores (rojo, verde, morado)
"""

import sys
import os
import time
import cv2
import numpy as np

sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))
from src.hardware import get_camera

def main():
    print("=== Prueba de Cámara ===")
    print("Inicializando cámara...")
    
    camera = get_camera(use_mock=False)
    if not camera.setup(width=640, height=480, format='RGB888'):
        print("Error: No se pudo inicializar la cámara")
        return
    
    camera.start()
    time.sleep(1)
    print("Cámara iniciada")
    
    # Rangos HSV para detección de colores
    hsv_ranges = {
        'ROJO': [
            (np.array([0, 120, 70]), np.array([10, 255, 255])),
            (np.array([170, 120, 70]), np.array([180, 255, 255]))
        ],
        'VERDE': [(np.array([40, 40, 40]), np.array([80, 255, 255]))],
        'MORADO': [(np.array([140, 50, 50]), np.array([170, 255, 255]))]
    }
    
    print("\nPrueba de detección de colores (Ctrl+C para salir)...\n")
    
    try:
        while True:
            frame = camera.capture_frame()
            if frame is None:
                continue
            
            # Convertir a BGR para OpenCV
            frame_bgr = cv2.cvtColor(frame, cv2.COLOR_RGB2BGR)
            hsv = cv2.cvtColor(frame_bgr, cv2.COLOR_BGR2HSV)
            
            detections = []
            
            for color_name, ranges in hsv_ranges.items():
                combined_mask = None
                
                for lower, upper in ranges:
                    mask = cv2.inRange(hsv, lower, upper)
                    if combined_mask is None:
                        combined_mask = mask
                    else:
                        combined_mask = cv2.bitwise_or(combined_mask, mask)
                
                # Filtrar ruido
                kernel = np.ones((5, 5), np.uint8)
                combined_mask = cv2.morphologyEx(combined_mask, cv2.MORPH_OPEN, kernel)
                
                # Encontrar contornos
                contours, _ = cv2.findContours(combined_mask, cv2.RETR_EXTERNAL, cv2.CHAIN_APPROX_SIMPLE)
                if contours:
                    c = max(contours, key=cv2.contourArea)
                    area = cv2.contourArea(c)
                    if area > 500:
                        M = cv2.moments(c)
                        if M["m00"] != 0:
                            cx = int(M["m10"] / M["m00"])
                            cy = int(M["m01"] / M["m00"])
                            detections.append((color_name, area, (cx, cy)))
            
            # Mostrar detecciones
            if detections:
                output = " | ".join([f"{name}: {area} px @ ({cx},{cy})" for name, area, (cx, cy) in detections])
                print(f"\r{output}", end='')
            else:
                print("\rSin detecciones...", end='')
            
            time.sleep(0.05)
            
    except KeyboardInterrupt:
        print("\nPrueba finalizada")
    finally:
        camera.stop()
        print("Cámara liberada")

if __name__ == "__main__":
    main()
