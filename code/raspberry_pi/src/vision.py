import cv2
import numpy as np
import logging
import threading
import time


def _deteccion_vacia(cx=0):
    """Detección por defecto cuando no se encuentra ningún color."""
    return {
        "color": "NINGUNO",
        "area": 0,
        "centroide_x": cx,
        "centroide_y": 0,
        "timestamp": time.monotonic(),
        "frame_id": 0
    }


class VisionProcessor:
    def __init__(self, config_loader):
        self.config = config_loader
        # Configuración de visión
        self.min_area = self.config.get_vision().get("min_area", 500)
        self.target_fps = 30  # Coincidir con framerate típico de cámara

        # Variables para procesamiento asíncrono
        self.lock = threading.Lock()
        self.latest_deteccion = _deteccion_vacia()
        self.corriendo = threading.Event()
        self.hilo_vision = None
        self.last_frame_time = 0
        self.frame_counter = 0

        # Odometría visual (Flujo Óptico)
        vision_config = self.config.get_vision()
        self.factor_px_cm = vision_config.get("factor_px_cm", 0.5)  # Calibración: 1 px = X cm
        self._velocidad_lock = threading.Lock()
        self._velocidad_cm_s = 0.0
        self._prev_gray = None
        self._prev_points = None
        self._prev_flow_time = None
        
    def iniciar_procesamiento_asincrono(self, cap):
        """Inicia el hilo de procesamiento de visión en segundo plano."""
        if self.hilo_vision is None or not self.hilo_vision.is_alive():
            self.corriendo.set()
            self.hilo_vision = threading.Thread(target=self._worker_vision, args=(cap,), daemon=True)
            self.hilo_vision.start()
            logging.info("Hilo de procesamiento de visión iniciado.")

    def detener_procesamiento_asincrono(self):
        """Detiene el hilo de procesamiento de visión."""
        self.corriendo.clear()
        if self.hilo_vision and self.hilo_vision.is_alive():
            self.hilo_vision.join(timeout=1.0)
            logging.info("Hilo de procesamiento de visión detenido.")

    def _worker_vision(self, cap):
        """Worker que procesa frames en segundo plano con rate limiting."""
        period = 1.0 / self.target_fps

        while self.corriendo.is_set():
            t_start = time.monotonic()

            try:
                # Picamera2 usa capture_array() en lugar de cap.read()
                frame = cap.capture_array()
                if frame is not None:
                    self.frame_counter += 1
                    # Convertir RGB→BGR para compatibilidad con código HSV actual
                    frame_bgr = cv2.cvtColor(frame, cv2.COLOR_RGB2BGR)
                    deteccion = self._procesar_frame_interno(frame_bgr)
                    self._calcular_velocidad(frame_bgr)
                    with self.lock:
                        self.latest_deteccion = deteccion
                    self.last_frame_time = t_start
            except (cv2.error, ValueError, TypeError, Exception) as e:
                logging.error(f"Error en worker de visión: {e}")

            # Rate limiting para coincidir con framerate de cámara
            elapsed = time.monotonic() - t_start
            sleep_time = period - elapsed
            if sleep_time > 0:
                time.sleep(sleep_time)

    def obtener_deteccion(self):
        """Retorna la última detección procesada (no bloqueante)."""
        with self.lock:
            return dict(self.latest_deteccion)

    def obtener_velocidad(self):
        """Retorna la velocidad lineal estimada en cm/s (no bloqueante)."""
        with self._velocidad_lock:
            return self._velocidad_cm_s

    def _calcular_velocidad(self, frame):
        """Calcula la velocidad de desplazamiento usando flujo óptico de Lucas-Kanade."""
        gray = cv2.cvtColor(frame, cv2.COLOR_BGR2GRAY)
        alto, ancho = gray.shape

        # Solo usar la mitad inferior (suelo visible)
        roi = gray[alto // 2:, :]
        now = time.monotonic()

        if self._prev_gray is None or self._prev_points is None or self._prev_flow_time is None:
            self._prev_gray = roi
            self._prev_points = self._detectar_puntos(roi)
            self._prev_flow_time = now
            return

        dt = now - self._prev_flow_time
        if dt <= 0.0:
            return

        # Calcular flujo óptico
        if self._prev_points is not None and len(self._prev_points) > 0:
            new_points, status, _ = cv2.calcOpticalFlowPyrLK(
                self._prev_gray, roi, self._prev_points, None,
                winSize=(21, 21), maxLevel=3,
                criteria=(cv2.TERM_CRITERIA_EPS | cv2.TERM_CRITERIA_COUNT, 30, 0.01)
            )

            if new_points is not None and status is not None:
                # Filtrar solo los puntos que fueron rastreados exitosamente
                good_old = self._prev_points[status.flatten() == 1]
                good_new = new_points[status.flatten() == 1]

                if len(good_new) > 3:
                    # Calcular desplazamiento promedio en Y (eje de avance del robot)
                    dy = good_new[:, 1] - good_old[:, 1]
                    desplazamiento_medio_px = float(np.median(dy))

                    # Convertir a cm/s
                    desplazamiento_cm = abs(desplazamiento_medio_px) * self.factor_px_cm
                    velocidad = desplazamiento_cm / dt

                    with self._velocidad_lock:
                        self._velocidad_cm_s = velocidad

        # Actualizar estado anterior
        self._prev_gray = roi
        self._prev_points = self._detectar_puntos(roi)
        self._prev_flow_time = now

    def _detectar_puntos(self, gray_roi):
        """Detecta puntos clave (esquinas) en la ROI para el flujo óptico."""
        puntos = cv2.goodFeaturesToTrack(
            gray_roi, maxCorners=100, qualityLevel=0.05,
            minDistance=10, blockSize=7
        )
        return puntos

    def _procesar_frame_interno(self, frame):
        """Lógica interna de procesamiento de frame."""
        if frame is None:
            return _deteccion_vacia()

        hsv_frame = cv2.cvtColor(frame, cv2.COLOR_BGR2HSV)
        alto, ancho = frame.shape[:2]
        centro_frame_x = ancho // 2

        # Configuración HSV rojo
        hsv_rojo = self.config.get_hsv_rojo()
        lower_rojo1 = np.array(hsv_rojo.get('lower', [0, 120, 70]))
        upper_rojo1 = np.array(hsv_rojo.get('upper', [10, 255, 255]))
        lower_rojo2 = np.array(hsv_rojo.get('lower2', [170, 120, 70]))
        upper_rojo2 = np.array(hsv_rojo.get('upper2', [180, 255, 255]))

        # Configuración HSV verde
        hsv_verde = self.config.get_hsv_verde()
        lower_verde = np.array(hsv_verde.get('lower', [40, 40, 40]))
        upper_verde = np.array(hsv_verde.get('upper', [80, 255, 255]))

        # Configuración HSV magenta (cajón de estacionamiento)
        hsv_magenta = self.config.get_hsv_magenta()
        lower_magenta = np.array(hsv_magenta.get('lower', [140, 50, 50]))
        upper_magenta = np.array(hsv_magenta.get('upper', [170, 255, 255]))

        # Creación de máscaras
        mask_rojo1 = cv2.inRange(hsv_frame, lower_rojo1, upper_rojo1)
        mask_rojo2 = cv2.inRange(hsv_frame, lower_rojo2, upper_rojo2)
        mask_rojo = cv2.bitwise_or(mask_rojo1, mask_rojo2)

        mask_verde = cv2.inRange(hsv_frame, lower_verde, upper_verde)
        mask_magenta = cv2.inRange(hsv_frame, lower_magenta, upper_magenta)

        # Filtrado de ruido (apertura morfológica) en un solo paso
        kernel = np.ones((5, 5), np.uint8)
        
        # Evaluar la mejor detección para cada color
        detecciones = [
            self._obtener_mejor_deteccion(cv2.morphologyEx(m, cv2.MORPH_OPEN, kernel), color)
            for m, color in [(mask_rojo, "ROJO"), (mask_verde, "VERDE"), (mask_magenta, "MAGENTA")]
        ]
        
        # Filtrar None
        validas = [d for d in detecciones if d is not None]

        if not validas:
            return _deteccion_vacia(centro_frame_x)

        # Retornar detección con área máxima
        deteccion = max(validas, key=lambda x: x["area"])
        # Agregar timestamp y frame_id
        deteccion["timestamp"] = time.monotonic()
        deteccion["frame_id"] = self.frame_counter
        return deteccion

    def _obtener_mejor_deteccion(self, mask, color_name):
        contours, _ = cv2.findContours(mask, cv2.RETR_EXTERNAL, cv2.CHAIN_APPROX_SIMPLE)
        if contours:
            c = max(contours, key=cv2.contourArea)
            area = cv2.contourArea(c)
            if area > self.min_area:
                M = cv2.moments(c)
                if M["m00"] != 0:
                    cx = int(M["m10"] / M["m00"])
                    cy = int(M["m01"] / M["m00"])
                    return {"color": color_name, "area": area, "centroide_x": cx, "centroide_y": cy}
        return None

