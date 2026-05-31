import cv2
import numpy as np
import logging

class VisionProcessor:
    def __init__(self, config_loader):
        self.config = config_loader
        # Mover min_area a config.yaml con valor por defecto
        self.min_area = self.config.get_vision().get("min_area", 500)
        
    def procesar_frame(self, frame):
        if frame is None:
            return {"color": "NINGUNO", "area": 0, "centroide_x": 0, "centroide_y": 0}
            
        hsv_frame = cv2.cvtColor(frame, cv2.COLOR_BGR2HSV)
        alto, ancho = frame.shape[:2]
        centro_frame_x = ancho // 2
        
        # Configuración Rojo
        hsv_rojo = self.config.get_hsv_rojo()
        lower_rojo1 = np.array(hsv_rojo.get('lower', [0, 120, 70]))
        upper_rojo1 = np.array(hsv_rojo.get('upper', [10, 255, 255]))
        lower_rojo2 = np.array(hsv_rojo.get('lower2', [170, 120, 70]))
        upper_rojo2 = np.array(hsv_rojo.get('upper2', [180, 255, 255]))
        
        # Configuración Verde
        hsv_verde = self.config.get_hsv_verde()
        lower_verde = np.array(hsv_verde.get('lower', [40, 40, 40]))
        upper_verde = np.array(hsv_verde.get('upper', [80, 255, 255]))

        # Configuración Magenta (Cajón de Estacionamiento)
        hsv_magenta = self.config.get_hsv_magenta()
        lower_magenta = np.array(hsv_magenta.get('lower', [140, 50, 50]))
        upper_magenta = np.array(hsv_magenta.get('upper', [170, 255, 255]))

        # Máscaras
        mask_rojo1 = cv2.inRange(hsv_frame, lower_rojo1, upper_rojo1)
        mask_rojo2 = cv2.inRange(hsv_frame, lower_rojo2, upper_rojo2)
        mask_rojo = cv2.bitwise_or(mask_rojo1, mask_rojo2)
        
        mask_verde = cv2.inRange(hsv_frame, lower_verde, upper_verde)
        mask_magenta = cv2.inRange(hsv_frame, lower_magenta, upper_magenta)
        
        # Filtrado de ruido
        kernel = np.ones((5,5), np.uint8)
        mask_rojo = cv2.morphologyEx(mask_rojo, cv2.MORPH_OPEN, kernel)
        mask_verde = cv2.morphologyEx(mask_verde, cv2.MORPH_OPEN, kernel)
        mask_magenta = cv2.morphologyEx(mask_magenta, cv2.MORPH_OPEN, kernel)
        
        # Analizar máscaras
        det_rojo = self._analizar_mascara(mask_rojo, "ROJO")
        det_verde = self._analizar_mascara(mask_verde, "VERDE")
        det_magenta = self._analizar_mascara(mask_magenta, "MAGENTA")
        
        # Filtrar detecciones por área
        detecciones = [det_rojo, det_verde, det_magenta]
        detecciones_validas = [d for d in detecciones if d["area"] > self.min_area]
        
        if not detecciones_validas:
            return {"color": "NINGUNO", "area": 0, "centroide_x": centro_frame_x, "centroide_y": 0}
            
        # Retornar la detección con el área máxima
        return max(detecciones_validas, key=lambda x: x["area"])

    def _analizar_mascara(self, mask, nombre_color):
        contours, _ = cv2.findContours(mask, cv2.RETR_EXTERNAL, cv2.CHAIN_APPROX_SIMPLE)
        if not contours:
            return {"color": nombre_color, "area": 0, "centroide_x": 0, "centroide_y": 0}
            
        max_contour = max(contours, key=cv2.contourArea)
        area = cv2.contourArea(max_contour)
        
        # Calcular centroide usando momentos de la imagen
        M = cv2.moments(max_contour)
        cx, cy = 0, 0
        if M["m00"] != 0:
            cx = int(M["m10"] / M["m00"])
            cy = int(M["m01"] / M["m00"])
            
        return {"color": nombre_color, "area": area, "centroide_x": cx, "centroide_y": cy}

