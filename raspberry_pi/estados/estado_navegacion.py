import time
import logging
from .fsm import Estado

class EstadoNavegacion(Estado):
    def enter(self, contexto: dict):
        super().enter(contexto)
        logging.info("Modo navegación autónoma iniciado.")
        
        # Cargar configuraciones de competición
        config_loader = contexto.get("config_loader")
        comp_config = config_loader.get_competicion()
        self.modo_reto = comp_config.get("modo_reto", "obstaculos")
        self.sentido_giro = comp_config.get("sentido_giro", "horario")
        self.max_vueltas = comp_config.get("max_vueltas", 3)
        
        lidar_config = config_loader.get_lidar()
        self.distancia_giro_cm = lidar_config.get("distancia_giro_cm", 50.0)
        
        # Variables de estado local para control de vueltas y giros
        self.vueltas = 0
        
        # Desafío Obstáculos
        self.detectando_estacionamiento = False
        self.frames_sin_magenta = 0
        
        # Desafío Abierto
        self.en_esquina = False
        self.conteo_esquinas = 0
        self.lecturas_fuera_esquina = 0

    def ejecutar(self, contexto: dict) -> str:
        cap = contexto.get("cap")
        vision = contexto.get("vision")
        arduino = contexto.get("arduino")
        lidar = contexto.get("lidar")
        velocidades = contexto.get("velocidades")
        angulos = contexto.get("angulos")

        if cap is None:
            logging.error("Cámara no disponible en contexto.")
            return "FIN"

        # Leer frame para procesamiento visual (aplicable en ambos modos para visualización/debug o detección magenta)
        ret, frame = cap.read()
        if not ret:
            logging.error("No se pudo leer el frame en navegación. Reintentando...")
            time.sleep(0.05)
            return "NAVEGACION"

        alto, ancho = frame.shape[:2]
        recto = angulos.get("recto", 90)

        if self.modo_reto == "obstaculos":
            # --- Modo Obstáculos ---
            deteccion = vision.procesar_frame(frame)
            color = deteccion["color"]
            cx = deteccion["centroide_x"]
            
            if color == "ROJO":
                vel = velocidades.get("evasion", 40)
                evasion_roja = angulos.get("evasion_roja", 130)
                # Dirección proporcional: más al centro del frame, mayor giro
                factor = max(0.0, min(1.0, 1.0 - (abs(cx - (ancho / 2)) / (ancho / 2))))
                ang = int(recto + factor * (evasion_roja - recto))
            elif color == "VERDE":
                vel = velocidades.get("evasion", 40)
                evasion_verde = angulos.get("evasion_verde", 50)
                # Dirección proporcional
                factor = max(0.0, min(1.0, 1.0 - (abs(cx - (ancho / 2)) / (ancho / 2))))
                ang = int(recto + factor * (evasion_verde - recto))
            elif color == "MAGENTA":
                vel = velocidades.get("crucero", 60)
                ang = recto
                
                # Conteo de vueltas basado en la detección de la zona de estacionamiento magenta
                if not self.detectando_estacionamiento:
                    self.detectando_estacionamiento = True
                    self.vueltas += 1
                    self.frames_sin_magenta = 0
                    logging.info(f"¡Zona de estacionamiento detectada! Vuelta {self.vueltas}/{self.max_vueltas}.")
                    
                    if self.vueltas >= self.max_vueltas:
                        logging.info("Carrera completada. Iniciando maniobra de estacionamiento...")
                        # Detener el robot momentáneamente
                        if arduino:
                            arduino.enviar_comando(0, recto)
                        return "ESTACIONAR"
            else:
                vel = velocidades.get("crucero", 60)
                ang = recto
                
                # Debounce para la salida de la zona de estacionamiento magenta
                if self.detectando_estacionamiento:
                    self.frames_sin_magenta += 1
                    if self.frames_sin_magenta > 15: # ~0.75 segundos sin ver magenta
                        self.detectando_estacionamiento = False

        else:
            # --- Modo Abierto (Muros con LiDAR) ---
            dist = -1.0
            if lidar:
                dist = lidar.leer_distancia()
                
            # Lógica de navegación del reto abierto
            if 0.0 < dist < self.distancia_giro_cm:
                # Evasión/giro en esquina
                vel = velocidades.get("evasion", 40)
                if self.sentido_giro == "horario":
                    ang = angulos.get("evasion_verde", 50) # Girar a la derecha
                else:
                    ang = angulos.get("evasion_roja", 130) # Girar a la izquierda
                
                # Detección y conteo de esquinas (4 esquinas = 1 vuelta completa)
                if not self.en_esquina:
                    self.en_esquina = True
                    self.conteo_esquinas += 1
                    self.vueltas = (self.conteo_esquinas - 1) // 4 + 1
                    self.lecturas_fuera_esquina = 0
                    logging.info(f"Esquina detectada ({self.conteo_esquinas}/12). Vuelta {self.vueltas}/{self.max_vueltas}.")
                    
                    if self.conteo_esquinas >= self.max_vueltas * 4:
                        logging.info("3 vueltas completadas en el Reto Abierto. Finalizando carrera...")
                        if arduino:
                            arduino.enviar_comando(0, recto)
                        return "FIN"
            else:
                # Navegación recta
                vel = velocidades.get("crucero", 60)
                ang = recto
                
                # Debounce para salir del estado de esquina
                if self.en_esquina:
                    self.lecturas_fuera_esquina += 1
                    if self.lecturas_fuera_esquina > 5: # 5 lecturas consecutivas seguras
                        self.en_esquina = False

        # Enviar comandos calculados al Arduino
        if arduino:
            arduino.enviar_comando(vel, ang)
            
        # Mantener loop estable a ~20 Hz
        time.sleep(0.05)
        return "NAVEGACION"

    def exit(self, contexto: dict):
        super().exit(contexto)
