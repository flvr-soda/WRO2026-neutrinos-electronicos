#!/usr/bin/env python3
"""
SISTEMA DE EMERGENCIA - Navegación simple por paredes negras
Objetivo: Completar 3 vueltas al circuito sin chocar con paredes negras
"""

import sys
import os
import time
import logging
import cv2
import numpy as np
import yaml
from picamera2 import Picamera2

# Agregar path para importar módulos del proyecto principal
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))
from raspberry_pi.src.comms_arduino import ArduinoComms

# Configuración de logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)

class EmergencyNavigator:
    """Navegador de emergencia simple para seguir paredes negras"""
    
    def __init__(self):
        # Cargar configuración
        self.load_config()
        
        # Configuración básica
        self.vueltas_completadas = 0
        self.vueltas_objetivo = self.config['navegacion']['vueltas_objetivo']
        self.ultimo_angulo = 90
        self.ultima_velocidad = 0
        
        # Parámetros de visión
        self.umbral_negro = self.config['vision']['umbral_negro']
        self.region_interes_y = self.config['vision']['region_interes_y']
        self.ancho_seguro = self.config['vision']['ancho_seguro']
        
        # Parámetros de movimiento
        self.velocidad_crucero = self.config['navegacion']['velocidad_crucero']
        self.velocidad_giro = self.config['navegacion']['velocidad_giro']
        self.angulo_recto = self.config['navegacion']['angulo_recto']
        self.angulo_giro_izq = self.config['navegacion']['angulo_giro_izquierda']
        self.angulo_giro_der = self.config['navegacion']['angulo_giro_derecha']
        self.duracion_giro = self.config['navegacion']['duracion_giro_seg']
        
        # Estado de detección de esquina
        self.en_esquina = False
        self.tiempo_inicio_giro = 0
        
        # Inicializar componentes
        self.init_camera()
        self.init_arduino()
        
    def load_config(self):
        """Cargar configuración desde config.yaml"""
        config_path = os.path.join(os.path.dirname(__file__), 'config.yaml')
        try:
            with open(config_path, 'r') as f:
                self.config = yaml.safe_load(f)
            logger.info(f"Configuración cargada desde {config_path}")
        except Exception as e:
            logger.error(f"Error cargando configuración: {e}")
            raise
        
    def init_camera(self):
        """Inicializar cámara CSI"""
        try:
            self.picam2 = Picamera2()
            config = self.picam2.create_video_configuration(
                main={
                    "format": "RGB888",
                    "size": (640, 480)
                }
            )
            self.picam2.configure(config)
            self.picam2.start()
            time.sleep(0.5)  # Esperar estabilización
            logger.info("Cámara inicializada")
        except Exception as e:
            logger.error(f"Error al inicializar cámara: {e}")
            raise
            
    def init_arduino(self):
        """Inicializar comunicación con Arduino"""
        try:
            self.arduino = ArduinoComms(baudrate=115200)
            time.sleep(1)  # Esperar conexión
            logger.info(f"Arduino conectado en {self.arduino.port}")
        except Exception as e:
            logger.error(f"Error al conectar Arduino: {e}")
            raise
            
    def detectar_paredes(self, frame):
        """
        Detectar paredes negras en el frame
        Retorna: (pared_izq, pared_der, distancia_centro)
        """
        # Convertir a escala de grises
        gray = cv2.cvtColor(frame, cv2.COLOR_RGB2GRAY)
        
        # Aplicar umbral para detectar negro
        _, binary = cv2.threshold(gray, self.umbral_negro, 255, cv2.THRESH_BINARY)
        
        # Extraer línea de escaneo horizontal
        linea = binary[self.region_interes_y, :]
        
        # Encontrar bordes de paredes negras
        # Buscar transiciones de negro (0) a blanco (255)
        ancho = len(linea)
        centro = ancho // 2
        
        # Detectar pared izquierda (buscar primer blanco desde izquierda)
        pared_izq = False
        for i in range(centro - self.ancho_seguro):
            if linea[i] > 127:  # Blanco = sin pared
                pared_izq = False
            else:  # Negro = pared
                pared_izq = True
                break
                
        # Detectar pared derecha (buscar primer blanco desde derecha)
        pared_der = False
        for i in range(ancho - 1, centro + self.ancho_seguro, -1):
            if linea[i] > 127:  # Blanco = sin pared
                pared_der = False
            else:  # Negro = pared
                pared_der = True
                break
                
        # Calcular distancia al centro del pasillo
        # Buscar el centro de la región blanca
        region_central = linea[centro - self.ancho_seguro:centro + self.ancho_seguro]
        if np.mean(region_central) < 127:
            # Centro oscuro = cerca de pared
            distancia_centro = -1  # Demasiado cerca
        else:
            distancia_centro = 1  # OK
            
        return pared_izq, pared_der, distancia_centro
        
    def calcular_comando(self, pared_izq, pared_der, distancia_centro):
        """
        Calcular comando de movimiento basado en detección de paredes
        Retorna: (velocidad, angulo)
        """
        # Si estamos en medio de un giro de esquina
        if self.en_esquina:
            if time.time() - self.tiempo_inicio_giro < self.duracion_giro:
                # Continuar giro
                return self.velocidad_giro, self.angulo_giro_der
            else:
                # Terminar giro
                self.en_esquina = False
                return self.velocidad_crucero, self.angulo_recto
        
        # Detectar esquina (ambas paredes presentes)
        if pared_izq and pared_der:
            logger.info("Esquina detectada - iniciando giro")
            self.en_esquina = True
            self.tiempo_inicio_giro = time.time()
            self.vueltas_completadas += 1
            logger.info(f"Vueltas completadas: {self.vueltas_completadas}/{self.vueltas_objetivo}")
            return self.velocidad_giro, self.angulo_giro_der
        
        # Navegación normal - mantenerse en el centro
        if pared_izq and not pared_der:
            # Pared izquierda detectada, girar derecha
            return self.velocidad_crucero, self.angulo_giro_der
        elif pared_der and not pared_izq:
            # Pared derecha detectada, girar izquierda
            return self.velocidad_crucero, self.angulo_giro_izq
        else:
            # Sin paredes cercanas, ir recto
            return self.velocidad_crucero, self.angulo_recto
            
    def enviar_comando(self, velocidad, angulo):
        """Enviar comando al Arduino"""
        try:
            self.arduino.enviar_comando(velocidad, angulo)
            self.ultimo_angulo = angulo
            self.ultima_velocidad = velocidad
        except Exception as e:
            logger.error(f"Error enviando comando: {e}")
            
    def detener(self):
        """Detener el robot"""
        self.enviar_comando(0, self.angulo_recto)
        logger.info("Robot detenido")
        
    def run(self):
        """Loop principal de navegación"""
        logger.info("Iniciando navegación de emergencia...")
        logger.info(f"Objetivo: {self.vueltas_objetivo} vueltas")
        
        try:
            while self.vueltas_completadas < self.vueltas_objetivo:
                # Capturar frame
                frame = self.picam2.capture_array()
                
                # Detectar paredes
                pared_izq, pared_der, distancia = self.detectar_paredes(frame)
                
                # Calcular comando
                velocidad, angulo = self.calcular_comando(pared_izq, pared_der, distancia)
                
                # Enviar comando
                self.enviar_comando(velocidad, angulo)
                
                # Pequeña pausa para no saturar
                time.sleep(0.05)
                
        except KeyboardInterrupt:
            logger.info("Interrupción por usuario")
        except Exception as e:
            logger.error(f"Error en loop principal: {e}")
        finally:
            self.detener()
            self.picam2.stop()
            logger.info("Navegación finalizada")
            
def main():
    """Función principal"""
    try:
        navigator = EmergencyNavigator()
        navigator.run()
    except Exception as e:
        logger.error(f"Error fatal: {e}")
        sys.exit(1)

if __name__ == "__main__":
    main()
