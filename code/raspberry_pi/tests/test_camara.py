#!/usr/bin/env python3
"""
Script de prueba para cámara CSI Raspberry Pi
Prueba captura de frames y detección de colores HSV
"""

import cv2
import numpy as np
import time
import sys
import os

# Agregar path para importar módulos
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))
from src.config_loader import ConfigLoader
from src.hardware import get_camera

# Cargar configuración
config_path = os.path.abspath(os.path.join(os.path.dirname(__file__), '..', 'config.yaml'))
config_loader = ConfigLoader(config_path)
vision_config = config_loader.get_vision()

# Configuración HSV desde config.yaml
HSV_ROJO_LOWER1 = np.array(config_loader.get_hsv_rojo().get('lower', [0, 120, 70]))
HSV_ROJO_UPPER1 = np.array(config_loader.get_hsv_rojo().get('upper', [10, 255, 255]))
HSV_ROJO_LOWER2 = np.array(config_loader.get_hsv_rojo().get('lower2', [170, 120, 70]))
HSV_ROJO_UPPER2 = np.array(config_loader.get_hsv_rojo().get('upper2', [180, 255, 255]))

HSV_VERDE_LOWER = np.array(config_loader.get_hsv_verde().get('lower', [40, 40, 40]))
HSV_VERDE_UPPER = np.array(config_loader.get_hsv_verde().get('upper', [80, 255, 255]))

HSV_MAGENTA_LOWER = np.array(config_loader.get_hsv_magenta().get('lower', [140, 50, 50]))
HSV_MAGENTA_UPPER = np.array(config_loader.get_hsv_magenta().get('upper', [170, 255, 255]))

MIN_AREA = vision_config.get('min_area', 500)

class CameraTester:
    """Clase reutilizable para pruebas de cámara"""
    
    def __init__(self, config_loader=None, use_mock=False):
        self.camera = None
        self.config_loader = config_loader
        self.use_mock = use_mock
        
    def setup(self):
        """Inicializa cámara usando configuración de config.yaml"""
        self.camera = get_camera(use_mock=self.use_mock)
        vision_config = self.config_loader.get_vision() if self.config_loader else {}
        
        width = vision_config.get('width', 640)
        height = vision_config.get('height', 480)
        format_str = vision_config.get('format', 'RGB888')
        
        if self.camera.setup(width=width, height=height, format=format_str):
            self.camera.start()
            time.sleep(1)  # Esperar estabilización
            return True
        return False
        
    def capture_frame(self):
        """Captura un frame y lo convierte a BGR"""
        if self.camera:
            frame = self.camera.capture_frame()
            if frame is not None:
                return cv2.cvtColor(frame, cv2.COLOR_RGB2BGR)
        return None
        
    def stop(self):
        """Detiene y libera la cámara"""
        if self.camera:
            self.camera.stop()

def detectar_colores(frame):
    """Detecta rojo, verde y magenta en el frame"""
    hsv = cv2.cvtColor(frame, cv2.COLOR_BGR2HSV)
    
    # Máscaras
    mask_rojo1 = cv2.inRange(hsv, HSV_ROJO_LOWER1, HSV_ROJO_UPPER1)
    mask_rojo2 = cv2.inRange(hsv, HSV_ROJO_LOWER2, HSV_ROJO_UPPER2)
    mask_rojo = cv2.bitwise_or(mask_rojo1, mask_rojo2)
    
    mask_verde = cv2.inRange(hsv, HSV_VERDE_LOWER, HSV_VERDE_UPPER)
    mask_magenta = cv2.inRange(hsv, HSV_MAGENTA_LOWER, HSV_MAGENTA_UPPER)
    
    # Filtrado de ruido
    kernel = np.ones((5, 5), np.uint8)
    mask_rojo = cv2.morphologyEx(mask_rojo, cv2.MORPH_OPEN, kernel)
    mask_verde = cv2.morphologyEx(mask_verde, cv2.MORPH_OPEN, kernel)
    mask_magenta = cv2.morphologyEx(mask_magenta, cv2.MORPH_OPEN, kernel)
    
    # Encontrar contornos
    detecciones = {}
    
    for mask, color_name in [(mask_rojo, "ROJO"), (mask_verde, "VERDE"), (mask_magenta, "MAGENTA")]:
        contours, _ = cv2.findContours(mask, cv2.RETR_EXTERNAL, cv2.CHAIN_APPROX_SIMPLE)
        if contours:
            c = max(contours, key=cv2.contourArea)
            area = cv2.contourArea(c)
            if area > MIN_AREA:
                M = cv2.moments(c)
                if M["m00"] != 0:
                    cx = int(M["m10"] / M["m00"])
                    cy = int(M["m01"] / M["m00"])
                    detecciones[color_name] = {"area": area, "centro": (cx, cy)}
                    cv2.drawContours(frame, [c], -1, (0, 255, 0), 2)
                    cv2.circle(frame, (cx, cy), 5, (0, 0, 255), -1)
    
    return frame, detecciones

def main(headless=True, use_mock=False):
    """Función principal de prueba individual de cámara
    
    Args:
        headless: Si True, ejecuta sin ventana gráfica (modo consola)
        use_mock: Si True, usa cámara simulada (para desarrollo en Windows)
    """
    print("Iniciando prueba de cámara CSI...")
    print(f"Modo: {'MOCK (simulado)' if use_mock else 'REAL (hardware)'}")
    print(f"Display: {'HEADLESS (sin ventana)' if headless else 'GRÁFICO (con ventana)'}")
    
    camera = CameraTester(config_loader, use_mock=use_mock)
    if not camera.setup():
        print("Error: No se pudo inicializar la cámara")
        return
    
    print("Cámara iniciada. Presiona Ctrl+C para salir.")
    print("-" * 60)
    
    try:
        while True:
            frame_bgr = camera.capture_frame()
            if frame_bgr is None:
                continue
                
            frame_con_detecciones, detecciones = detectar_colores(frame_bgr)
            
            if headless:
                # Modo headless: mostrar detecciones por consola
                if detecciones:
                    print("\r" + " " * 60, end='')  # Limpiar línea
                    y_offset = 0
                    for color, data in detecciones.items():
                        texto = f"{color}: Area={data['area']}, Centro={data['centro']}"
                        print(f"\r{texto}", end='')
                else:
                    print("\rSin detecciones...", end='')
            else:
                # Modo gráfico: mostrar ventana
                y_offset = 30
                for color, data in detecciones.items():
                    texto = f"{color}: Area={data['area']}, Centro={data['centro']}"
                    cv2.putText(frame_con_detecciones, texto, (10, y_offset),
                               cv2.FONT_HERSHEY_SIMPLEX, 0.6, (255, 255, 255), 2)
                    y_offset += 25
                
                cv2.imshow("Test Cámara - Presiona 'q' para salir", frame_con_detecciones)
                
                if cv2.waitKey(1) & 0xFF == ord('q'):
                    break
                
    except KeyboardInterrupt:
        print("\nInterrupción por usuario")
    finally:
        camera.stop()
        if not headless:
            cv2.destroyAllWindows()
        print("Cámara liberada.")

if __name__ == "__main__":
    import sys
    # Permitir cambiar modo con argumentos de línea de comandos
    headless_mode = True  # Default: headless
    use_mock_mode = False  # Default: real hardware
    
    if len(sys.argv) > 1:
        if sys.argv[1] == '--gui':
            headless_mode = False
        elif sys.argv[1] == '--mock':
            use_mock_mode = True
        elif sys.argv[1] == '--mock-gui':
            use_mock_mode = True
            headless_mode = False
    
    main(headless=headless_mode, use_mock=use_mock_mode)
