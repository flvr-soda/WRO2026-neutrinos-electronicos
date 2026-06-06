import time
import logging
from .fsm import Estado

class EstadoEstacionar(Estado):
    def enter(self, contexto: dict):
        super().enter(contexto)
        logging.info("Maniobra de estacionamiento iniciada.")
        
        # --- Configuración del LiDAR ---
        config_loader = contexto.get("config_loader")
        lidar_config = config_loader.get_lidar()
        self.umbral_hueco_cm = lidar_config.get("umbral_hueco_cm", 80.0)
        self.distancia_pared_cm = lidar_config.get("distancia_pared_cm", 30.0)
        self.angulo_inicio = lidar_config.get("angulo_escaneo_inicio", 45)
        self.angulo_fin = lidar_config.get("angulo_escaneo_fin", 135)
        self.paso = lidar_config.get("paso_escaneo", 15)
        
        # --- Fases de Estacionamiento ---
        self.fase = "escaneo"  # escaneo, aproximacion, reversa, enderezar, completado
        self.tiempo_inicio_fase = time.time()
        self.intentos_escaneo = 0
        self.max_intentos_escaneo = 5
        
        # --- Parámetros de Movimiento ---
        self.velocidades = contexto.get("velocidades", {})
        self.angulos = contexto.get("angulos", {})
        self.recto = self.angulos.get("recto", 90)
        self.evasion_izq = self.angulos.get("evasion_roja", 130)
        self.evasion_der = self.angulos.get("evasion_verde", 50)
        self.vel_lenta = self.velocidades.get("evasion", 40)
        self.vel_reversa = 30  # Velocidad fija para reversa (cm/s)

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
        
        # --- Detener Robot para Escaneo ---
        try:
            arduino.enviar_comando(0, self.recto)
        except Exception as e:
            logging.error(f"Error al detener robot para escaneo: {e}")
        time.sleep(0.5)
        
        # --- Escanear Entorno con LiDAR ---
        try:
            mapa = lidar.escanear_entorno(self.angulo_inicio, self.angulo_fin, self.paso)
            logging.info(f"Mapa LiDAR: {mapa}")
        except Exception as e:
            logging.error(f"Error al escanear entorno con LiDAR: {e}")
            mapa = []
        
        # --- Buscar Hueco de Estacionamiento ---
        hueco_encontrado = False
        for i in range(len(mapa) - 2):
            ang1, dist1 = mapa[i]
            ang2, dist2 = mapa[i + 1]
            ang3, dist3 = mapa[i + 2]
            
# Hueco detectado: 3 lecturas consecutivas con distancia > umbral
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
        # --- Avanzar y Reintentar Escaneo ---
            try:
                arduino.enviar_comando(self.vel_lenta, self.recto)
            except Exception as e:
                logging.error(f"Error al avanzar para reintentar escaneo: {e}")
            time.sleep(1.0)
        
        return "ESTACIONAR"
    
    def _fase_aproximacion(self, arduino):
        """Se aproxima al hueco y se alinea."""
        logging.info("Fase: Aproximación y alineación.")
        
        # --- Avanzar Lentamente hacia el Hueco ---
        try:
            arduino.enviar_comando(self.vel_lenta, self.recto)
        except Exception as e:
            logging.error(f"Error al avanzar en aproximación: {e}")
        time.sleep(1.5)  # Avanzar por 1.5 segundos (aprox. 60 cm a 40 cm/s)
        
        # --- Girar para Alinearse con el Hueco ---
        try:
            arduino.enviar_comando(self.vel_lenta, self.evasion_der)
        except Exception as e:
            logging.error(f"Error al girar en aproximación: {e}")
        time.sleep(0.8)
        
        # --- Detener Momentáneamente ---
        try:
            arduino.enviar_comando(0, self.recto)
        except Exception as e:
            logging.error(f"Error al detener en aproximación: {e}")
        time.sleep(0.3)
        
        self.fase = "reversa"
        self.tiempo_inicio_fase = time.time()
        logging.info("Aproximación completada, iniciando reversa.")
        return "ESTACIONAR"
    
    def _fase_reversa(self, lidar, arduino):
        """Realiza la maniobra de reversa dentro del hueco."""
        logging.info("Fase: Reversa dentro del hueco.")
        
        # --- Girar Ruedas para Reversa en Ángulo ---
        try:
            arduino.enviar_comando(self.vel_reversa, self.evasion_der)
        except Exception as e:
            logging.error(f"Error al girar para reversa: {e}")
        time.sleep(1.2)
        
        # --- Enderezar y Continuar Reversa ---
        try:
            arduino.enviar_comando(self.vel_reversa, self.recto)
        except Exception as e:
            logging.error(f"Error al enderezar en reversa: {e}")
        time.sleep(1.0)
        
        # --- Girar en Sentido Opuesto para Enderezar ---
        try:
            arduino.enviar_comando(self.vel_reversa, self.evasion_izq)
        except Exception as e:
            logging.error(f"Error al girar opuesto en reversa: {e}")
        time.sleep(0.8)
        
        # --- Detener Momentáneamente ---
        try:
            arduino.enviar_comando(0, self.recto)
        except Exception as e:
            logging.error(f"Error al detener en reversa: {e}")
        time.sleep(0.3)
        
        # --- Verificar Distancia a la Pared ---
        try:
            lidar.apuntar_servo(90)  # Apuntar al frente (ángulo recto)
            time.sleep(0.2)
            dist_frente = lidar.leer_distancia()
        except Exception as e:
            logging.error(f"Error al leer distancia con LiDAR en reversa: {e}")
            dist_frente = -1.0
        
        if dist_frente > 0 and dist_frente < self.distancia_pared_cm + 10:
            logging.info(f"Distancia a pared: {dist_frente} cm. Ajustando posición.")
        # --- Ajustar Posición si Está Muy Cerca ---
            try:
                arduino.enviar_comando(20, self.recto)
            except Exception as e:
                logging.error(f"Error al ajustar posición en reversa: {e}")
            time.sleep(0.5)
        
        self.fase = "enderezar"
        self.tiempo_inicio_fase = time.time()
        logging.info("Reversa completada, enderezando.")
        return "ESTACIONAR"
    
    def _fase_enderezar(self, arduino):
        """Endereza el robot dentro del cajón de estacionamiento."""
        logging.info("Fase: Enderezar posición final.")
        
        # --- Avanzar Ligeramente para Centrarse ---
        try:
            arduino.enviar_comando(self.vel_lenta, self.recto)
        except Exception as e:
            logging.error(f"Error al avanzar en enderezar: {e}")
        time.sleep(0.5)
        
        # --- Detener Completamente ---
        try:
            arduino.enviar_comando(0, self.recto)
        except Exception as e:
            logging.error(f"Error al detener en enderezar: {e}")
        time.sleep(0.3)
        
        self.fase = "completado"
        logging.info("Posición final enderezada.")
        return "ESTACIONAR"

    def exit(self, contexto: dict):
        super().exit(contexto)
        # --- Asegurar Detención del Robot ---
        arduino = contexto.get("arduino")
        if arduino:
            try:
                arduino.enviar_comando(0, 90)
            except Exception as e:
                logging.error(f"Error al detener robot al salir de estacionamiento: {e}")
        logging.info("Estado de estacionamiento finalizado.")
