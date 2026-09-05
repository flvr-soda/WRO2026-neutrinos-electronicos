#!/usr/bin/env python3
"""
Test Completo - Prueba integrada de todos los componentes del robot
Prueba: Ultrasonido, MPU, LiDAR con servo, Cámara, Motor, Servo de dirección
"""

import sys
import os
import time

sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))
from src.comms_arduino import ArduinoComms
from src.hardware import get_servo, get_camera

def test_ultrasonico(arduino):
    """Prueba de HC-SR04 vía Arduino"""
    print("\n" + "="*50)
    print("PRUEBA 1: HC-SR04 (Ultrasónico)")
    print("="*50)
    
    try:
        print("Leyendo distancia ultrasónica (3 segundos)...")
        start_time = time.time()
        lecturas = []
        
        while time.time() - start_time < 3:
            telemetria = arduino.obtener_telemetria()
            if telemetria:
                dist = telemetria.get('dist_trasera', -1)
                if dist >= 0:
                    lecturas.append(dist)
                    print(f"Distancia: {dist:.1f} cm", end='\r')
            time.sleep(0.1)
        
        if lecturas:
            avg = sum(lecturas) / len(lecturas)
            print(f"\n✓ Ultrasónico funcionando - Promedio: {avg:.1f} cm")
            return True
        else:
            print("\n✗ No se obtuvieron lecturas válidas")
            return False
    except Exception as e:
        print(f"\n✗ Error: {e}")
        return False

def test_mpu(arduino):
    """Prueba de MPU6050 vía Arduino"""
    print("\n" + "="*50)
    print("PRUEBA 2: MPU6050 (Giroscopio)")
    print("="*50)
    
    try:
        print("Leyendo giroscopio (3 segundos)...")
        start_time = time.time()
        lecturas = []
        
        while time.time() - start_time < 3:
            telemetria = arduino.obtener_telemetria()
            if telemetria:
                z = telemetria.get('z', 0)
                lecturas.append(z)
                print(f"Giro Z: {z:.1f}°", end='\r')
            time.sleep(0.1)
        
        if lecturas:
            print(f"\n✓ MPU6050 funcionando - Último valor: {lecturas[-1]:.1f}°")
            return True
        else:
            print("\n✗ No se obtuvieron lecturas válidas")
            return False
    except Exception as e:
        print(f"\n✗ Error: {e}")
        return False

def test_lidar():
    """Prueba de LiDAR TF-Luna con servo de paneo"""
    print("\n" + "="*50)
    print("PRUEBA 3: LiDAR TF-Luna con Servo")
    print("="*50)
    
    import serial
    import struct
    
    LIDAR_PORT = "/dev/serial0"
    LIDAR_BAUD = 115200
    SERVO_PIN = 18
    
    try:
        # Inicializar servo
        print("Inicializando servo...")
        servo = get_servo(use_mock=False)
        if not servo.setup(SERVO_PIN, frequency=50):
            print("✗ Error: No se pudo inicializar el servo")
            return False
        
        servo.set_angle(90)
        time.sleep(0.5)
        
        # Conectar LiDAR
        print(f"Conectando a LiDAR en {LIDAR_PORT}...")
        ser = serial.Serial(LIDAR_PORT, LIDAR_BAUD, timeout=1)
        time.sleep(2)
        
        def read_distance():
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
        
        # Prueba de lectura continua
        print("Leyendo LiDAR (2 segundos)...")
        start_time = time.time()
        lecturas = []
        
        while time.time() - start_time < 2:
            dist = read_distance()
            if dist > 0:
                lecturas.append(dist)
                print(f"Distancia: {dist:.1f} cm", end='\r')
            time.sleep(0.1)
        
        # Prueba de escaneo
        print("\nEscaneando LiDAR (90°)...")
        servo.set_angle(90)
        time.sleep(0.3)
        dist = read_distance()
        
        servo.cleanup()
        ser.close()
        
        if lecturas:
            avg = sum(lecturas) / len(lecturas)
            print(f"\n✓ LiDAR funcionando - Promedio: {avg:.1f} cm")
            return True
        else:
            print("\n✗ No se obtuvieron lecturas válidas")
            return False
    except Exception as e:
        print(f"\n✗ Error: {e}")
        return False

def test_camara():
    """Prueba de cámara con detección de colores"""
    print("\n" + "="*50)
    print("PRUEBA 4: Cámara (Detección de Colores)")
    print("="*50)
    
    try:
        print("Inicializando cámara...")
        camera = get_camera(use_mock=False)
        if not camera.setup(width=640, height=480, format='RGB888'):
            print("✗ Error: No se pudo inicializar la cámara")
            return False
        
        camera.start()
        time.sleep(1)
        
        print("Capturando frames (2 segundos)...")
        start_time = time.time()
        frames = 0
        
        while time.time() - start_time < 2:
            frame = camera.capture_frame()
            if frame is not None:
                frames += 1
                print(f"Frames capturados: {frames}", end='\r')
            time.sleep(0.05)
        
        camera.stop()
        
        if frames > 0:
            print(f"\n✓ Cámara funcionando - Capturados {frames} frames")
            return True
        else:
            print("\n✗ No se capturaron frames")
            return False
    except Exception as e:
        print(f"\n✗ Error: {e}")
        return False

def test_motor(arduino):
    """Prueba de motor vía Arduino"""
    print("\n" + "="*50)
    print("PRUEBA 5: Motor")
    print("="*50)
    
    try:
        print("Probando motor...")
        
        # Secuencia de prueba
        print("1. Detenido")
        arduino.enviar_comando(0, 90)
        time.sleep(1)
        
        print("2. Avance lento (30%)")
        arduino.enviar_comando(30, 90)
        time.sleep(1)
        
        print("3. Detenido")
        arduino.enviar_comando(0, 90)
        time.sleep(1)
        
        print("✓ Motor funcionando")
        return True
    except Exception as e:
        print(f"✗ Error: {e}")
        return False

def test_servo_direccion(arduino):
    """Prueba de servo de dirección vía Arduino"""
    print("\n" + "="*50)
    print("PRUEBA 6: Servo de Dirección")
    print("="*50)
    
    try:
        print("Probando servo de dirección...")
        
        # Secuencia de prueba
        print("1. Centrado (90°)")
        arduino.enviar_comando(0, 90)
        time.sleep(1)
        
        print("2. Derecha (50°)")
        arduino.enviar_comando(0, 50)
        time.sleep(1)
        
        print("3. Izquierda (130°)")
        arduino.enviar_comando(0, 130)
        time.sleep(1)
        
        print("4. Centrado (90°)")
        arduino.enviar_comando(0, 90)
        time.sleep(1)
        
        print("✓ Servo de dirección funcionando")
        return True
    except Exception as e:
        print(f"✗ Error: {e}")
        return False

def main():
    print("="*50)
    print("TEST COMPLETO DEL ROBOT")
    print("="*50)
    print("Este script prueba todos los componentes del robot")
    print("Presiona Ctrl+C para interrumpir en cualquier momento\n")
    
    resultados = {}
    
    # Conectar Arduino (usado por ultrasonido, MPU, motor, servo)
    print("Conectando a Arduino...")
    arduino = ArduinoComms(baudrate=115200)
    time.sleep(2)
    
    if not arduino.esta_conectado():
        print("✗ Error: No se pudo conectar al Arduino")
        return
    
    print(f"✓ Conectado a Arduino en {arduino.port}\n")
    
    try:
        # Ejecutar pruebas
        resultados['ultrasonico'] = test_ultrasonico(arduino)
        resultados['mpu'] = test_mpu(arduino)
        resultados['lidar'] = test_lidar()
        resultados['camara'] = test_camara()
        resultados['motor'] = test_motor(arduino)
        resultados['servo_direccion'] = test_servo_direccion(arduino)
        
        # Resumen
        print("\n" + "="*50)
        print("RESUMEN DE RESULTADOS")
        print("="*50)
        
        for componente, resultado in resultados.items():
            estado = "✓ PASS" if resultado else "✗ FAIL"
            print(f"{componente:20s}: {estado}")
        
        total = len(resultados)
        pasados = sum(resultados.values())
        print(f"\nTotal: {pasados}/{total} pruebas pasadas")
        
        if pasados == total:
            print("¡Todas las pruebas pasaron!")
        else:
            print(f"Algunas pruebas fallaron. Revisa los componentes marcados con ✗")
        
    except KeyboardInterrupt:
        print("\n\nPrueba interrumpida por usuario")
    finally:
        # Detener motores y cerrar conexiones
        arduino.enviar_comando(0, 90)
        time.sleep(0.5)
        arduino.cerrar()
        print("\nRecursos liberados")

if __name__ == "__main__":
    main()
