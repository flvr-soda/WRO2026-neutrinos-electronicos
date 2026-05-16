import cv2
import numpy as np
import logging

class VisionProcessor:
    def __init__(self, config_loader):
        self.config = config_loader
        self.min_area = 500 # Umbral mínimo de píxeles para evitar ruido
        
    def procesar_frame(self, frame):
        if frame is None:
            return "NINGUNO"
            
        hsv_frame = cv2.cvtColor(frame, cv2.COLOR_BGR2HSV)
        
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

        # Máscaras
        mask_rojo1 = cv2.inRange(hsv_frame, lower_rojo1, upper_rojo1)
        mask_rojo2 = cv2.inRange(hsv_frame, lower_rojo2, upper_rojo2)
        mask_rojo = cv2.bitwise_or(mask_rojo1, mask_rojo2)
        
        mask_verde = cv2.inRange(hsv_frame, lower_verde, upper_verde)
        
        # Filtrado de ruido
        kernel = np.ones((5,5), np.uint8)
        mask_rojo = cv2.morphologyEx(mask_rojo, cv2.MORPH_OPEN, kernel)
        mask_verde = cv2.morphologyEx(mask_verde, cv2.MORPH_OPEN, kernel)
        
        # Contornos y Áreas
        area_rojo = self._get_max_contour_area(mask_rojo)
        area_verde = self._get_max_contour_area(mask_verde)
        
        # Lógica de decisión
        if area_rojo > self.min_area and area_rojo > area_verde:
            return "ROJO"
        elif area_verde > self.min_area and area_verde > area_rojo:
            return "VERDE"
        else:
            return "NINGUNO"

    def _get_max_contour_area(self, mask):
        contours, _ = cv2.findContours(mask, cv2.RETR_EXTERNAL, cv2.CHAIN_APPROX_SIMPLE)
        if not contours:
            return 0
        max_contour = max(contours, key=cv2.contourArea)
        return cv2.contourArea(max_contour)
