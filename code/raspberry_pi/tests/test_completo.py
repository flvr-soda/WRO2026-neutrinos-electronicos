#!/usr/bin/env python3
"""
Script de prueba combinado para sensores principales
Prueba cámara, MPU6050 y servo de dirección simultáneamente
"""

import cv2
import time
import threading
import sys
import os

sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))
from src.config_loader import ConfigLoader

config_path = os.path.abspath(os.path.join(os.path.dirname(__file__), '..', 'config.yaml'))
config_loader = ConfigLoader(config_path)

from test_camara import CameraTester, detectar_colores
from test_lidar import LidarTester
from test_ultrasonico import UltrasonicoTester

def main(headless=True):
    """Función principal de prueba combinada
    
    Args:
        headless: Si True, ejecuta sin ventana gráfica (modo consola)
    """
    print("=" * 60)
    print("Test Completo de Sensores - Terreneitor WRO 2026")
    print(f"Modo: {'HEADLESS (sin ventana)' if headless else 'GRÁFICO (con ventana)'}")
    print("=" * 60)
    
    # Inicializar sensores
    camera = CameraTester(config_loader)
    camera.setup()
    
    ultrasonico = UltrasonicoTester(config_loader)
    arduino_ok = ultrasonico.setup()
    
    lidar = LidarTester(config_loader)
    lidar_ok = lidar.setup()
    
    if not arduino_ok:
        print("WARNING: Arduino no disponible. Continuando sin telemetría.")
    if not lidar_ok:
        print("WARNING: LiDAR no disponible. Continuando sin LiDAR.")
    
    # Variables compartidas
    lidar_distance = -1.0
    lidar_angle = 90
    running = True
    lock = threading.Lock()
    
    # Hilo Arduino
    def arduino_loop():
        while running:
            ultrasonico.read_telemetry()
            time.sleep(0.05)
    
    # Hilo LiDAR
    def lidar_loop():
        nonlocal lidar_distance
        while running:
            dist = lidar.read_distance()
            with lock:
                lidar_distance = dist
            time.sleep(0.05)
    
    thread_arduino = threading.Thread(target=arduino_loop, daemon=True)
    thread_lidar = threading.Thread(target=lidar_loop, daemon=True)
    thread_arduino.start()
    thread_lidar.start()
    
    # Obtener ángulos de configuración
    angulos_config = config_loader.get_angulos_servo()
    velocidades_config = config_loader.get_velocidades()
    recto = angulos_config.get('recto', 90)
    giro_derecha = angulos_config.get('giro_derecha', 50)
    giro_izquierda = angulos_config.get('giro_izquierda', 130)
    velocidad_test = velocidades_config.get('evasion', 40)
    
    print("\nSistema iniciado. Presiona Ctrl+C para salir.")
    if not headless:
        print("Controles:")
        print("  [1-5]: Escanear LiDAR a diferentes ángulos")
        print("  [c]:   Centrar servo LiDAR")
        print("  [d]:   Girar servo dirección a la DERECHA")
        print("  [i]:   Girar servo dirección a la IZQUIERDA")
        print("  [r]:   Centrar servo dirección (recto)")
        print("  [q]:   Salir")
    print("-" * 60)

    try:
        lidar_angles = [45, 60, 75, 90, 105, 120, 135]
        current_lidar_idx = 3
        
        while running:
            frame_bgr = camera.capture_frame()
            if frame_bgr is None:
                continue
            
            frame_con_detecciones, detecciones = detectar_colores(frame_bgr)
            
            # Obtener telemetría Arduino
            arduino_telemetry = ultrasonico.get_latest_telemetry()
            z_grados = arduino_telemetry.get('z', 0)
            angulo_servo = arduino_telemetry.get('angulo', 90)
            dist_trasera = arduino_telemetry.get('dist_trasera', -1.0)
            vueltas = int(abs(z_grados) / 360.0)
            
            if headless:
                # Modo headless: mostrar info por consola
                info = f"MPU: Z={z_grados:.1f}° V={vueltas} | "
                info += f"Servo: {angulo_servo}° | "
                info += f"Ultrasonido: {dist_trasera:.1f}cm | "
                info += f"LiDAR: {lidar_distance:.1f}cm @ {lidar_angle}° | "
                if detecciones:
                    for color, data in detecciones.items():
                        info += f"{color}: Area={data['area']} "
                else:
                    info += "Sin detecciones"
                print(f"\r{info}", end='')
            else:
                # Modo gráfico: mostrar ventana
                y_offset = 30
                
                # Info Arduino
                cv2.putText(frame_con_detecciones, f"Arduino: Z={z_grados:.1f}° A={angulo_servo}° U={dist_trasera:.1f}cm",
                           (10, y_offset), cv2.FONT_HERSHEY_SIMPLEX, 0.5, (255, 255, 255), 2)
                y_offset += 25
                
                # Info LiDAR
                with lock:
                    lidar_text = f"LiDAR: {lidar_distance:.1f}cm @ {lidar_angle}°" if lidar_distance > 0 else "LiDAR: Sin lectura"
                cv2.putText(frame_con_detecciones, lidar_text,
                           (10, y_offset), cv2.FONT_HERSHEY_SIMPLEX, 0.5, (255, 255, 255), 2)
                y_offset += 25
                
                # Info Visión
                for color, data in detecciones.items():
                    texto = f"{color}: Area={data['area']} Centro={data['centro']}"
                    cv2.putText(frame_con_detecciones, texto, (10, y_offset),
                               cv2.FONT_HERSHEY_SIMPLEX, 0.5, (0, 255, 0), 2)
                    y_offset += 20
                
                cv2.imshow("Test Completo - Sensores", frame_con_detecciones)
                
                key = cv2.waitKey(1) & 0xFF
                
                if key == ord('q'):
                    break
                elif key == ord('c') and lidar_ok:
                    lidar.set_servo_angle(90)
                    lidar_angle = 90
                    current_lidar_idx = 3
                elif key == ord('d') and arduino_ok:
                    ultrasonico.enviar_comando(velocidad_test, giro_derecha)
                    print(f"\rServo dirección: DERECHA ({giro_derecha}°)", end='')
                elif key == ord('i') and arduino_ok:
                    ultrasonico.enviar_comando(velocidad_test, giro_izquierda)
                    print(f"\rServo dirección: IZQUIERDA ({giro_izquierda}°)", end='')
                elif key == ord('r') and arduino_ok:
                    ultrasonico.enviar_comando(0, recto)
                    print(f"\rServo dirección: RECTO ({recto}°)", end='')
                elif key in [ord('1'), ord('2'), ord('3'), ord('4'), ord('5')] and lidar_ok:
                    idx = key - ord('1')
                    if idx < len(lidar_angles):
                        lidar.set_servo_angle(lidar_angles[idx])
                        lidar_angle = lidar_angles[idx]
                        current_lidar_idx = idx
                    
    except KeyboardInterrupt:
        print("\nInterrupción por usuario")
    finally:
        running = False
        camera.stop()
        ultrasonico.stop()
        lidar.stop()
        if not headless:
            cv2.destroyAllWindows()
        print("\nRecursos liberados.")

if __name__ == "__main__":
    # Permitir cambiar modo con argumento de línea de comandos
    headless_mode = True  # Default: headless
    if len(sys.argv) > 1 and sys.argv[1] == '--gui':
        headless_mode = False
    main(headless=headless_mode)
