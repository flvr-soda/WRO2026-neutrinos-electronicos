#!/usr/bin/env python3
"""
Script de prueba para LiDAR TF-Luna
Prueba lectura de distancia y control de servo
"""

import serial
import time
import struct
import sys
import os

# Agregar path para importar módulos
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))
from src.config_loader import ConfigLoader
from src.hardware import get_servo

# Cargar configuración
config_path = os.path.abspath(os.path.join(os.path.dirname(__file__), '..', 'config.yaml'))
config_loader = ConfigLoader(config_path)
serial_ports_config = config_loader.get_serial_ports()
lidar_config = config_loader.get_lidar()

# Configuración desde config.yaml
LIDAR_PORT = serial_ports_config.get('lidar', '/dev/serial0')
LIDAR_BAUDRATE = 115200
SERVO_PIN = lidar_config.get('pin_servo', 18)

class LidarTester:
    """Clase reutilizable para pruebas de LiDAR TF-Luna"""
    
    def __init__(self, config_loader=None, use_mock=False):
        if config_loader:
            serial_ports_config = config_loader.get_serial_ports()
            lidar_config = config_loader.get_lidar()
            self.port = serial_ports_config.get('lidar', '/dev/serial0')
            self.servo_pin = lidar_config.get('pin_servo', 18)
        else:
            self.port = '/dev/serial0'
            self.servo_pin = 18
        self.baudrate = 115200
        self.ser = None
        self.servo = None
        self.current_angle = 90
        self.config_loader = config_loader
        self.use_mock = use_mock
        
    def setup(self):
        """Inicializa LiDAR y servo"""
        try:
            # Setup servo usando hardware abstraction layer
            self.servo = get_servo(use_mock=self.use_mock)
            if self.servo.setup(self.servo_pin, frequency=50):
                print("Centrando servo a 90 grados...")
                self.set_servo_angle(90)
                time.sleep(0.5)
            else:
                print("WARNING: Servo no disponible. Control de servo deshabilitado.")
                self.servo = None
            
            # Setup LiDAR serial
            print(f"Conectando a LiDAR en {self.port}...")
            self.ser = serial.Serial(self.port, self.baudrate, timeout=1)
            time.sleep(2)
            print("LiDAR conectado exitosamente")
            return True
        except Exception as e:
            print(f"Error iniciando LiDAR: {e}")
            return False
            
    def set_servo_angle(self, angle):
        """Mueve servo a ángulo específico (0-180)"""
        if self.servo:
            self.servo.set_angle(angle)
            self.current_angle = angle
        else:
            # Simulation mode - just update the angle
            self.current_angle = max(0, min(180, angle))
            
    def read_distance(self):
        """Lee distancia del TF-Luna en cm"""
        if not self.ser:
            return -1.0
        try:
            # Leer todos los bytes disponibles
            bytes_waiting = self.ser.in_waiting
            if bytes_waiting >= 9:
                data = self.ser.read(bytes_waiting)
                # Buscar header 0x59 0x59
                for i in range(len(data) - 8):
                    if data[i] == 0x59 and data[i+1] == 0x59:
                        # Extraer frame de 9 bytes
                        frame = data[i:i+9]
                        if len(frame) == 9:
                            # TF-Luna no valida checksum por defecto, ignorarlo
                            # Extraer distancia (bytes 2-3, little-endian)
                            dist_cm = struct.unpack('<H', frame[2:4])[0]
                            signal_quality = frame[1]
                            if signal_quality > 30:
                                return dist_cm
        except Exception as e:
            print(f"DEBUG: Error leyendo LiDAR: {e}")
        return -1.0
        
    def scan(self, start_angle=None, end_angle=None, step=None, verbose=True):
        """Escanea LiDAR en rango de ángulos (ida y vuelta). Retorna lista de (angulo, distancia)."""
        if self.config_loader:
            lidar_config = self.config_loader.get_lidar()
            start_angle = start_angle or lidar_config.get('angulo_escaneo_inicio', 45)
            end_angle = end_angle or lidar_config.get('angulo_escaneo_fin', 135)
            step = step or lidar_config.get('paso_escaneo', 15)
            distancia_pared = lidar_config.get('distancia_pared_cm', 30)
        else:
            start_angle = start_angle or 45
            end_angle = end_angle or 135
            step = step or 15
            distancia_pared = 30
        if verbose:
            print(f"\nEscaneando LiDAR (barrido completo): {start_angle}° -> {end_angle}° -> {start_angle}°...")
            print(f"Umbral de obstáculo: {distancia_pared} cm")
        
        resultados = []
        obstaculos = []
        
        # Ida: de start_angle a end_angle
        for angle in range(start_angle, end_angle + 1, step):
            self.set_servo_angle(angle)
            time.sleep(0.2)
            
            lecturas = []
            for _ in range(3):
                dist = self.read_distance()
                if dist > 0:
                    lecturas.append(dist)
                time.sleep(0.05)
            
            if lecturas:
                avg_dist = sum(lecturas) / len(lecturas)
                resultados.append((angle, avg_dist))
                
                # Determinar dirección
                if angle < 70:
                    direccion = "IZQUIERDA"
                elif angle > 110:
                    direccion = "DERECHA"
                else:
                    direccion = "FRENTE"
                
                # Detectar obstáculo
                if avg_dist < distancia_pared:
                    obstaculo = f"OBSTACULO CERCANO a {avg_dist:.1f} cm en {direccion} ({angle}°)"
                    obstaculos.append(obstaculo)
                    if verbose:
                        print(f"  Ángulo {angle}° ({direccion}): {avg_dist:.1f} cm - {obstaculo}")
                else:
                    if verbose:
                        print(f"  Ángulo {angle}° ({direccion}): {avg_dist:.1f} cm - Libre")
            elif verbose:
                print(f"  Ángulo {angle}°: Sin lectura válida")
        
        # Vuelta: de end_angle a start_angle (excluyendo extremos ya medidos)
        for angle in range(end_angle - step, start_angle, -step):
            self.set_servo_angle(angle)
            time.sleep(0.2)
            
            lecturas = []
            for _ in range(3):
                dist = self.read_distance()
                if dist > 0:
                    lecturas.append(dist)
                time.sleep(0.05)
            
            if lecturas:
                avg_dist = sum(lecturas) / len(lecturas)
                resultados.append((angle, avg_dist))
                
                # Determinar dirección
                if angle < 70:
                    direccion = "IZQUIERDA"
                elif angle > 110:
                    direccion = "DERECHA"
                else:
                    direccion = "FRENTE"
                
                # Detectar obstáculo
                if avg_dist < distancia_pared:
                    obstaculo = f"OBSTACULO CERCANO a {avg_dist:.1f} cm en {direccion} ({angle}°)"
                    obstaculos.append(obstaculo)
                    if verbose:
                        print(f"  Ángulo {angle}° ({direccion}): {avg_dist:.1f} cm - {obstaculo}")
                else:
                    if verbose:
                        print(f"  Ángulo {angle}° ({direccion}): {avg_dist:.1f} cm - Libre")
            elif verbose:
                print(f"  Ángulo {angle}°: Sin lectura válida")
        
        # Resumen de obstáculos
        if verbose and obstaculos:
            print("\n" + "=" * 50)
            print("RESUMEN DE OBSTACULOS:")
            for obs in obstaculos:
                print(f"  {obs}")
            print("=" * 50)
        elif verbose:
            print("\nNo se detectaron obstaculos cercanos.")
        
        # Centrar servo
        self.set_servo_angle(90)
        if self.servo:
            self.servo.stop()
        
        return resultados
        
    def stop(self):
        """Detiene y libera recursos"""
        # Centrar servo al frente antes de detener
        self.set_servo_angle(90)
        time.sleep(0.2)
        
        if self.ser:
            self.ser.close()
        if self.servo:
            self.servo.cleanup()

def main():
    """Función principal de prueba individual de LiDAR"""
    print("Iniciando prueba de LiDAR TF-Luna...")
    
    lidar = LidarTester(config_loader)
    if not lidar.setup():
        return
    
    print(f"Conectado a LiDAR en {lidar.port}")
    
    try:
        # Prueba de lectura continua
        print("\nPrueba de lectura continua (5 segundos)...")
        start_time = time.time()
        while time.time() - start_time < 5:
            dist = lidar.read_distance()
            if dist > 0:
                print(f"Distancia: {dist:.1f} cm", end='\r')
            time.sleep(0.1)
        print("\n")
        
        # Prueba de escaneo con servo
        resultados = lidar.scan()
        
        print("\nResumen del escaneo:")
        for angle, dist in resultados:
            print(f"  {angle}°: {dist:.1f} cm")
        
    except KeyboardInterrupt:
        print("\nInterrupción por usuario")
    finally:
        lidar.stop()
        print("Recursos liberados.")

if __name__ == "__main__":
    main()
