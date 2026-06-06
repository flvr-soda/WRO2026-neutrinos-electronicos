import cv2
import numpy as np
import logging
import threading

class VisionProcessor:
    def __init__(self, config_loader):
        self.config = config_loader
        # --- Configuración de Visión ---
        self.min_area = self.config.get_vision().get("min_area", 500)
        
        # --- Variables para Procesamiento Asíncrono ---
        self.lock = threading.Lock()
        self.latest_deteccion = {"color": "NINGUNO", "area": 0, "centroide_x": 0, "centroide_y": 0}
        self.corriendo = False
        self.hilo_vision = None
        
    def iniciar_procesamiento_asincrono(self, cap):
        """Inicia el hilo de procesamiento de visión en segundo plano."""
        if self.hilo_vision is None or not self.hilo_vision.is_alive():
            self.corriendo = True
            self.hilo_vision = threading.Thread(target=self._worker_vision, args=(cap,), daemon=True)
            self.hilo_vision.start()
            logging.info("Hilo de procesamiento de visión iniciado.")
    
    def detener_procesamiento_asincrono(self):
        """Detiene el hilo de procesamiento de visión."""
        self.corriendo = False
        if self.hilo_vision and self.hilo_vision.is_alive():
            self.hilo_vision.join(timeout=1.0)
            logging.info("Hilo de procesamiento de visión detenido.")
    
    def _worker_vision(self, cap):
        """Worker que procesa frames en segundo plano."""
        while self.corriendo:
            try:
                ret, frame = cap.read()
                if ret:
                    deteccion = self._procesar_frame_interno(frame)
                    with self.lock:
                        self.latest_deteccion = deteccion
            except Exception as e:
                logging.error(f"Error en worker de visión: {e}")
            # Pequeño sleep para no saturar CPU
            threading.Event().wait(0.01)
    
    def obtener_deteccion(self):
        """Retorna la última detección procesada (no bloqueante)."""
        with self.lock:
            return dict(self.latest_deteccion)
    
    def procesar_frame(self, frame):
        """Método síncrono original (para compatibilidad)."""
        return self._procesar_frame_interno(frame)
    
    def _procesar_frame_interno(self, frame):
        """Lógica interna de procesamiento de frame."""
        if frame is None:
            return {"color": "NINGUNO", "area": 0, "centroide_x": 0, "centroide_y": 0}
            
        hsv_frame = cv2.cvtColor(frame, cv2.COLOR_BGR2HSV)
        alto, ancho = frame.shape[:2]
        centro_frame_x = ancho // 2
        
        # --- Configuración HSV Rojo ---
        hsv_rojo = self.config.get_hsv_rojo()
        lower_rojo1 = np.array(hsv_rojo.get('lower', [0, 120, 70]))
        upper_rojo1 = np.array(hsv_rojo.get('upper', [10, 255, 255]))
        lower_rojo2 = np.array(hsv_rojo.get('lower2', [170, 120, 70]))
        upper_rojo2 = np.array(hsv_rojo.get('upper2', [180, 255, 255]))
        
        # --- Configuración HSV Verde ---
        hsv_verde = self.config.get_hsv_verde()
        lower_verde = np.array(hsv_verde.get('lower', [40, 40, 40]))
        upper_verde = np.array(hsv_verde.get('upper', [80, 255, 255]))

        # --- Configuración HSV Magenta (Cajón de Estacionamiento) ---
        hsv_magenta = self.config.get_hsv_magenta()
        lower_magenta = np.array(hsv_magenta.get('lower', [140, 50, 50]))
        upper_magenta = np.array(hsv_magenta.get('upper', [170, 255, 255]))

        # --- Creación de Máscaras ---
        mask_rojo1 = cv2.inRange(hsv_frame, lower_rojo1, upper_rojo1)
        mask_rojo2 = cv2.inRange(hsv_frame, lower_rojo2, upper_rojo2)
        mask_rojo = cv2.bitwise_or(mask_rojo1, mask_rojo2)
        
        mask_verde = cv2.inRange(hsv_frame, lower_verde, upper_verde)
        mask_magenta = cv2.inRange(hsv_frame, lower_magenta, upper_magenta)
        
        # --- Filtrado de Ruido ---
        kernel = np.ones((5,5), np.uint8)
        mask_rojo = cv2.morphologyEx(mask_rojo, cv2.MORPH_OPEN, kernel)
        mask_verde = cv2.morphologyEx(mask_verde, cv2.MORPH_OPEN, kernel)
        mask_magenta = cv2.morphologyEx(mask_magenta, cv2.MORPH_OPEN, kernel)
        
        # --- Análisis de Máscaras ---
        det_rojo = self._analizar_mascara(mask_rojo, "ROJO")
        det_verde = self._analizar_mascara(mask_verde, "VERDE")
        det_magenta = self._analizar_mascara(mask_magenta, "MAGENTA")
        
        # --- Filtrado de Detecciones por Área ---
        detecciones = [det_rojo, det_verde, det_magenta]
        detecciones_validas = [d for d in detecciones if d["area"] > self.min_area]
        
        if not detecciones_validas:
            return {"color": "NINGUNO", "area": 0, "centroide_x": centro_frame_x, "centroide_y": 0}
            
        # --- Retornar Detección con Área Máxima ---
        return max(detecciones_validas, key=lambda x: x["area"])

    def _analizar_mascara(self, mask, nombre_color):
        contours, _ = cv2.findContours(mask, cv2.RETR_EXTERNAL, cv2.CHAIN_APPROX_SIMPLE)
        if not contours:
            return {"color": nombre_color, "area": 0, "centroide_x": 0, "centroide_y": 0}
            
        max_contour = max(contours, key=cv2.contourArea)
        area = cv2.contourArea(max_contour)
        
        # --- Cálculo de Centroide ---
        M = cv2.moments(max_contour)
        cx, cy = 0, 0
        if M["m00"] != 0:
            cx = int(M["m10"] / M["m00"])
            cy = int(M["m01"] / M["m00"])
            
        return {"color": nombre_color, "area": area, "centroide_x": cx, "centroide_y": cy}

