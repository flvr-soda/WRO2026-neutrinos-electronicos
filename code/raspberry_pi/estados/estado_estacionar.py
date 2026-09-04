import time
import logging
import serial
from .fsm import Estado

class EstadoEstacionar(Estado):
    def enter(self, contexto: dict):
        super().enter(contexto)
        logging.info("Maniobra de estacionamiento iniciada.")
        
        # Configuración del LiDAR
        config_loader = contexto.get("config_loader")
        lidar_config = config_loader.get_lidar()
        self.umbral_hueco_cm = lidar_config.get("umbral_hueco_cm", 55.0)
        self.distancia_pared_cm = lidar_config.get("distancia_pared_cm", 40.0)
        self.angulo_inicio = lidar_config.get("angulo_escaneo_inicio", 45)
        self.angulo_fin = lidar_config.get("angulo_escaneo_fin", 135)
        self.paso = lidar_config.get("paso_escaneo", 15)
        
        # Configuración del vehículo
        vehiculo_config = config_loader.get_vehiculo()
        self.largo_vehiculo_cm = vehiculo_config.get("largo_cm", 27.0)
        self.ancho_atras_cm = vehiculo_config.get("ancho_atras_cm", 17.0)
        
        # Calcular tiempos de maniobra basados en dimensiones
        # Tiempo para avanzar el largo del vehículo a velocidad lenta (40 cm/s)
        self.tiempo_avance_largo_s = self.largo_vehiculo_cm / 40.0  # ~0.68s para 27cm
        # Distancia crítica trasera: ancho trasero + margen de seguridad (5cm)
        self.distancia_trasera_critica_cm = self.ancho_atras_cm + 5.0  # 22cm
        
        # Fases de Estacionamiento
        self.fase = "escaneo"  # escaneo, aproximacion, reversa, enderezar, completado
        self.tiempo_inicio_fase = time.time()
        self.intentos_escaneo = 0
        self.max_intentos_escaneo = 5
        
        # Parámetros de Movimiento
        self.velocidades = contexto.get("velocidades", {})
        self.angulos = contexto.get("angulos", {})
        self.recto = self.angulos.get("recto", 90)
        self.evasion_izq = self.angulos.get("giro_izquierda", 130)
        self.evasion_der = self.angulos.get("giro_derecha", 50)
        self.vel_lenta = self.velocidades.get("evasion", 40)
        self.vel_reversa = -30  # Velocidad de reversa (negativa: el firmware invierte el puente H)

    def _mover(self, arduino, vel, ang, espera, etapa):
        """Envía un comando al Arduino con manejo de errores y espera opcional."""
        try:
            arduino.enviar_comando(vel, ang)
        except (AttributeError, serial.SerialException) as e:
            logging.error(f"Error al {etapa}: {e}")
        if espera > 0:
            time.sleep(espera)

    def ejecutar(self, contexto: dict) -> str:
        arduino = contexto.get("arduino")
        lidar = contexto.get("lidar")
        
        if not arduino or not lidar:
            logging.error("Arduino o LiDAR no disponibles. Abortando estacionamiento.")
            return "FIN"
        
        if self.fase == "escaneo":
            return self._fase_escaneo(lidar, arduino)
        elif self.fase == "aproximacion":
            return self._fase_aproximacion(arduino)
        elif self.fase == "reversa":
            return self._fase_reversa(lidar, arduino)
        elif self.fase == "enderezar":
            return self._fase_enderezar(arduino)
        elif self.fase == "completado":
            logging.info("Estacionamiento completado exitosamente.")
            return "FIN"
        
        return "ESTACIONAR"
    
    def _fase_escaneo(self, lidar, arduino):
        """Escanea el entorno buscando un hueco para estacionar."""
        logging.info("Fase: Escaneo de hueco de estacionamiento.")
        
        # Detener Robot para Escaneo
        self._mover(arduino, 0, self.recto, 0.5, "detener robot para escaneo")
        
        # Escanear Entorno con LiDAR
        try:
            mapa = lidar.escanear_entorno(self.angulo_inicio, self.angulo_fin, self.paso)
            logging.info(f"Mapa LiDAR: {mapa}")
        except (AttributeError, ValueError) as e:
            logging.error(f"Error al escanear entorno con LiDAR: {e}")
            mapa = []
        
        # Buscar Hueco de Estacionamiento
        # Hueco detectado: 3 lecturas consecutivas con distancia > umbral
        hueco_encontrado = False
        for i in range(len(mapa) - 2):
            _, dist1 = mapa[i]
            ang2, dist2 = mapa[i + 1]
            _, dist3 = mapa[i + 2]
            if (dist1 > self.umbral_hueco_cm and
                dist2 > self.umbral_hueco_cm and
                dist3 > self.umbral_hueco_cm):
                hueco_encontrado = True
                logging.info(f"Hueco detectado en ángulo {ang2}°")
                break
        
        if hueco_encontrado:
            self.fase = "aproximacion"
            self.tiempo_inicio_fase = time.time()
            logging.info("Hueco encontrado, iniciando aproximación.")
        else:
            self.intentos_escaneo += 1
            if self.intentos_escaneo >= self.max_intentos_escaneo:
                logging.warning("No se encontró hueco después de varios intentos. Abortando.")
                return "FIN"
            logging.info(f"No se encontró hueco. Intento {self.intentos_escaneo}/{self.max_intentos_escaneo}")
            # Avanzar y Reintentar Escaneo
            self._mover(arduino, self.vel_lenta, self.recto, 1.0, "avanzar para reintentar escaneo")
        
        return "ESTACIONAR"
    
    def _fase_aproximacion(self, arduino):
        """Se aproxima al hueco y se alinea."""
        logging.info("Fase: Aproximación y alineación.")
        
        # Avanzar lentamente hacia el hueco (basado en largo del vehículo)
        self._mover(arduino, self.vel_lenta, self.recto, self.tiempo_avance_largo_s, "avanzar en aproximación")
        # Girar para alinearse con el hueco (tiempo reducido)
        self._mover(arduino, self.vel_lenta, self.evasion_der, 0.5, "girar en aproximación")
        # Detener momentáneamente
        self._mover(arduino, 0, self.recto, 0.3, "detener en aproximación")
        
        self.fase = "reversa"
        self.tiempo_inicio_fase = time.time()
        logging.info("Aproximación completada, iniciando reversa.")
        return "ESTACIONAR"
    
    def _fase_reversa(self, lidar, arduino):
        """Realiza la maniobra de reversa dinámica dentro del hueco usando odometría y ultrasonido."""
        logging.info("Fase: Reversa dinámica (HC-SR04 + MPU6050)")
        
        telemetria_inicial = arduino.obtener_telemetria()
        z_inicial = telemetria_inicial.get("z", 0)
        
        # Timeout de seguridad por paso (evita bloqueo infinito si el sensor falla)
        TIMEOUT_PASO_S = 5.0
        
        # Paso 1: Girar ruedas para reversa en ángulo
        logging.info("Reversa paso 1: Girar a la derecha")
        self._mover(arduino, self.vel_reversa, self.evasion_der, 0, "girar para reversa")
        t_paso = time.time()
        while True:
            telemetria = arduino.obtener_telemetria()
            z_actual = telemetria.get("z", 0)
            dist_trasera = telemetria.get("dist_trasera", -1.0)
            
            if abs(z_actual - z_inicial) >= 30: # 30 grados de inclinación
                break
            if dist_trasera > 0 and dist_trasera < 5.0:
                logging.warning("Pared trasera detectada en paso 1. Abortando giro.")
                break
            if time.time() - t_paso > TIMEOUT_PASO_S:
                logging.warning("Timeout en paso 1 de reversa.")
                break
            time.sleep(0.05)

        # Paso 2: Reversa recta para meterse
        logging.info("Reversa paso 2: Recto hacia atrás")
        self._mover(arduino, self.vel_reversa, self.recto, 0, "enderezar en reversa")
        t_paso = time.time()
        while True:
            telemetria = arduino.obtener_telemetria()
            dist_trasera = telemetria.get("dist_trasera", -1.0)
            
            # Usar distancia crítica basada en ancho trasero
            if dist_trasera > 0 and dist_trasera < self.distancia_pared_cm:
                break
            if time.time() - t_paso > TIMEOUT_PASO_S:
                logging.warning("Timeout en paso 2 de reversa.")
                break
            time.sleep(0.05)

        # Paso 3: Girar en sentido opuesto para enderezar
        logging.info("Reversa paso 3: Girar a la izquierda")
        self._mover(arduino, self.vel_reversa, self.evasion_izq, 0, "girar opuesto en reversa")
        t_paso = time.time()
        while True:
            telemetria = arduino.obtener_telemetria()
            z_actual = telemetria.get("z", 0)
            dist_trasera = telemetria.get("dist_trasera", -1.0)
            
            if abs(z_actual - z_inicial) <= 5: # Paralelo otra vez
                break
            if dist_trasera > 0 and dist_trasera < self.distancia_trasera_critica_cm:
                logging.warning(f"Pared trasera a límite crítico ({self.distancia_trasera_critica_cm}cm). Deteniendo maniobra.")
                break
            if time.time() - t_paso > TIMEOUT_PASO_S:
                logging.warning("Timeout en paso 3 de reversa.")
                break
            time.sleep(0.05)
            
        # Detener momentáneamente
        self._mover(arduino, 0, self.recto, 0.3, "detener en reversa")
        
        # Ajuste fino final: Centrar entre ambas paredes
        telemetria = arduino.obtener_telemetria()
        dist_trasera = telemetria.get("dist_trasera", -1.0)
        
        try:
            lidar.apuntar_servo(90)  # Apuntar al frente
            time.sleep(0.2)
            dist_frente = lidar.leer_distancia()
        except (AttributeError, ValueError) as e:
            logging.error(f"Error al leer LiDAR en ajuste: {e}")
            dist_frente = -1.0
            
        logging.info(f"Ajuste final: Frente={dist_frente}cm, Trasera={dist_trasera}cm")
        
        if dist_frente > 0 and dist_frente < self.distancia_pared_cm + 5:
            self._mover(arduino, 20, self.recto, 0.5, "ajustar posición alejándose de frente")
        elif dist_trasera > 0 and dist_trasera < self.distancia_trasera_critica_cm:
            self._mover(arduino, 20, self.recto, 0.5, "ajustar posición alejándose de atrás")
        
        self.fase = "enderezar"
        self.tiempo_inicio_fase = time.time()
        logging.info("Reversa dinámica completada.")
        return "ESTACIONAR"
    
    def _fase_enderezar(self, arduino):
        """Endereza el robot dentro del cajón de estacionamiento."""
        logging.info("Fase: Enderezar posición final.")
        
        # Avanzar ligeramente para centrarse
        self._mover(arduino, self.vel_lenta, self.recto, 0.5, "avanzar en enderezar")
        # Detener completamente
        self._mover(arduino, 0, self.recto, 0.3, "detener en enderezar")
        
        self.fase = "completado"
        logging.info("Posición final enderezada.")
        return "ESTACIONAR"

    def exit(self, contexto: dict):
        super().exit(contexto)
        # Asegurar Detención del Robot
        arduino = contexto.get("arduino")
        if arduino:
            self._mover(arduino, 0, 90, 0, "detener robot al salir de estacionamiento")
