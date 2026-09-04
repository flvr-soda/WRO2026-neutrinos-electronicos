#!/usr/bin/env python3
"""
Script de prueba para HC-SR04 vía Arduino
Lee telemetría del ultrasónico desde el Arduino
"""

import serial
import re
import time
import sys
import os

# Agregar path para importar ConfigLoader
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))
from src.config_loader import ConfigLoader

# Cargar configuración
config_path = os.path.abspath(os.path.join(os.path.dirname(__file__), '..', 'config.yaml'))
config_loader = ConfigLoader(config_path)
serial_ports_config = config_loader.get_serial_ports()

# Configuración desde config.yaml
ARDUINO_PORT = serial_ports_config.get('arduino', '/dev/ttyUSB0')
ARDUINO_BAUDRATE = 115200

# Regex para parsear telemetría: T:Z:<grados>;A:<angulo>;U:<dist_trasera>;
TELEMETRIA_REGEX = re.compile(r"T:Z:(-?\d+(?:\.\d+)?);A:(\d+);U:(-?\d+(?:\.\d+)?);")

class UltrasonicoTester:
    """Clase reutilizable para pruebas de HC-SR04 vía Arduino"""
    
    def __init__(self, config_loader=None):
        if config_loader:
            serial_ports_config = config_loader.get_serial_ports()
            self.port = serial_ports_config.get('arduino', '/dev/ttyUSB0')
        else:
            self.port = '/dev/ttyUSB0'
        self.baudrate = 115200
        self.ser = None
        self.latest_telemetria = {"z": 0, "angulo": 90, "dist_trasera": -1.0}
        
    def setup(self):
        """Inicializa conexión serial con Arduino"""
        try:
            self.ser = serial.Serial(self.port, self.baudrate, timeout=1)
            time.sleep(2)  # Esperar reinicio del Arduino
            return True
        except serial.SerialException as e:
            print(f"Error conectando al Arduino: {e}")
            return False
            
    def read_telemetry(self):
        """Lee y parsea telemetría del Arduino"""
        if not self.ser:
            return None
        try:
            if self.ser.in_waiting > 0:
                linea = self.ser.readline().decode('utf-8').strip()
                if linea.startswith("T:"):
                    match = TELEMETRIA_REGEX.search(linea)
                    if match:
                        z_val, ang_val, dist_val = match.groups()
                        self.latest_telemetria = {
                            "z": float(z_val),
                            "angulo": int(ang_val),
                            "dist_trasera": float(dist_val)
                        }
                        return dict(self.latest_telemetria)
        except Exception:
            pass
        return None
        
    def get_latest_telemetry(self):
        """Retorna la última telemetría leída"""
        return dict(self.latest_telemetria)
        
    def enviar_comando(self, velocidad, angulo):
        """Envía comando de velocidad y ángulo al Arduino"""
        if not self.ser:
            return
        try:
            comando = f"V:{velocidad};A:{angulo}\n"
            self.ser.write(comando.encode('utf-8'))
            self.ser.flush()
        except Exception as e:
            print(f"Error enviando comando: {e}")
        
    def stop(self):
        """Cierra conexión serial"""
        if self.ser:
            self.ser.close()

def main():
    """Función principal de prueba individual de HC-SR04"""
    print("Iniciando prueba de HC-SR04 vía Arduino...")
    print(f"Conectando a Arduino en {ARDUINO_PORT}...")
    
    ultrasonico = UltrasonicoTester(config_loader)
    if not ultrasonico.setup():
        return
    
    print("Conectado al Arduino.")
    
    print("\nLeyendo telemetría del HC-SR04 (presiona Ctrl+C para salir)...")
    print("Formato: Z=giroscopio, A=ángulo servo, U=distancia ultrasónico (cm)")
    print("-" * 60)
    
    try:
        while True:
            telemetria = ultrasonico.read_telemetry()
            if telemetria:
                z = telemetria["z"]
                ang = telemetria["angulo"]
                dist = telemetria["dist_trasera"]
                
                if dist >= 0:
                    print(f"Z: {z:7.1f}° | A: {ang:3d}° | U: {dist:6.1f} cm", end='\r')
                else:
                    print(f"Z: {z:7.1f}° | A: {ang:3d}° | U: Fuera de rango  ", end='\r')
            
            time.sleep(0.05)  # 20Hz
            
    except serial.SerialException as e:
        print(f"\nError de conexión serial: {e}")
        print("Asegúrate de que el Arduino esté conectado y el puerto sea correcto.")
    except KeyboardInterrupt:
        print("\n\nInterrupción por usuario")
    finally:
        ultrasonico.stop()
        print("Conexión serial cerrada.")

if __name__ == "__main__":
    main()
