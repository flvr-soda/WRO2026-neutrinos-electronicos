import time
import logging
from .fsm import Estado

class EstadoNavegacion(Estado):
    def enter(self, contexto: dict):
        super().enter(contexto)
        logging.info("Modo navegación autónoma iniciado.")
        
        # --- Configuración de Competición ---
        config_loader = contexto.get("config_loader")
        comp_config = config_loader.get_competicion()
        self.modo_reto = comp_config.get("modo_reto", "obstaculos")
        self.sentido_giro = comp_config.get("sentido_giro", "horario")
        self.max_vueltas = comp_config.get("max_vueltas", 3)
        self.perimetro_pista_cm = comp_config.get("perimetro_pista_cm", 1200)
        self.tiempo_limite_segundos = comp_config.get("tiempo_limite_segundos", 180)  # Regla 9.25.1
        self.distancia_seccion_arranque_cm = comp_config.get("distancia_seccion_arranque_cm", 300)  # Regla 9.22
        self.retorno_arranque_habilitado = comp_config.get("retorno_arranque_habilitado", True)  # Regla 9.22
        self.distancia_seccion_meta_cm = comp_config.get("distancia_seccion_meta_cm", 300)  # Regla 9.25.2
        self.deteccion_violacion_senales = comp_config.get("deteccion_violacion_senales", True)  # Regla 9.25.5
        
        lidar_config = config_loader.get_lidar()
        self.distancia_giro_cm = lidar_config.get("distancia_giro_cm", 50.0)
        
        # --- Variables de Estado para Conteo de Vueltas ---
        self.vueltas = 0
        self.distancia_inicial_cm = 0
        self.distancia_ultima_vuelta_cm = 0
        
        # --- Variables para Retorno a Sección de Arranque (Regla 9.22) ---
        self.retornando_arranque = False
        self.distancia_objetivo_retorno = 0
        
        # --- Variables para Detección de Sección de Meta (Regla 9.25.2, Reto Abierto) ---
        self.detectando_meta = False
        self.distancia_objetivo_meta = 0
        
        # --- Variables para Detección de Violación de Señales (Regla 9.25.5) ---
        self.violaciones_senales = 0
        self.ultima_deteccion_color = None
        
        # --- Detección de Zona de Estacionamiento (Reto Obstáculos) ---
        self.detectando_estacionamiento = False
        self.frames_sin_magenta = 0
        
        # --- Estrategia de Navegación (Regla Sorpresa) ---
        self.estrategia = contexto.get("estrategia", None)
        if self.estrategia:
            logging.info(f"Estrategia de navegación cargada: {self.estrategia.get_nombre()}")
        else:
            logging.warning("No se cargó ninguna estrategia de navegación.")
        
        # --- Inicio de Ronda (Regla 9.25.1) ---
        self.tiempo_inicio_ronda = time.time()
        logging.info(f"Límite de tiempo: {self.tiempo_limite_segundos} segundos")
        logging.info(f"Retorno a sección de arranque: {'Habilitado' if self.retorno_arranque_habilitado else 'Deshabilitado'}")
        
        # --- Procesamiento Asíncrono de Visión ---
        vision = contexto.get("vision")
        cap = contexto.get("cap")
        if vision and cap:
            vision.iniciar_procesamiento_asincrono(cap)

    def ejecutar(self, contexto: dict) -> str:
        import time
        
        # --- Verificación de Límite de Tiempo (Regla 9.25.1) ---
        tiempo_transcurrido = time.time() - self.tiempo_inicio_ronda
        if tiempo_transcurrido > self.tiempo_limite_segundos:
            logging.warning(f"Tiempo límite agotado ({tiempo_transcurrido:.1f}s > {self.tiempo_limite_segundos}s)")
            arduino = contexto.get("arduino")
            if arduino:
                arduino.enviar_comando(0, 90)  # Detener motores
            return "FIN"
        
        cap = contexto.get("cap")
        vision = contexto.get("vision")
        arduino = contexto.get("arduino")
        lidar = contexto.get("lidar")
        velocidades = contexto.get("velocidades")
        angulos = contexto.get("angulos")

        if cap is None:
            logging.error("Cámara no disponible en contexto.")
            return "FIN"

        # --- Lectura de Frame de Cámara ---
        try:
            ret, frame = cap.read()
            if not ret:
                logging.warning("No se pudo leer el frame en navegación. Reintentando...")
                time.sleep(0.05)
                return "NAVEGACION"
        except Exception as e:
            logging.error(f"Error al leer frame de cámara: {e}")
            time.sleep(0.05)
            return "NAVEGACION"

        alto, ancho = frame.shape[:2]
        recto = angulos.get("recto", 90)
        
        # --- Telemetría del Encoder ---
        try:
            telemetria = arduino.obtener_telemetria() if arduino else {}
            distancia_actual_cm = telemetria.get("dist", 0)
        except Exception as e:
            logging.error(f"Error al obtener telemetría del Arduino: {e}")
            telemetria = {}
            distancia_actual_cm = 0
        
        # --- Inicialización de Distancia de Referencia ---
        if self.distancia_inicial_cm == 0:
            self.distancia_inicial_cm = distancia_actual_cm
            self.distancia_ultima_vuelta_cm = distancia_actual_cm
            logging.info(f"Distancia inicial del encoder: {distancia_actual_cm} cm")
        
        # --- Cálculo de Vueltas ---
        distancia_recorrida_cm = distancia_actual_cm - self.distancia_inicial_cm
        vueltas_completas = int(distancia_recorrida_cm / self.perimetro_pista_cm)
        
        # --- Detección de Nueva Vuelta ---
        if vueltas_completas > self.vueltas:
            self.vueltas = vueltas_completas
            self.distancia_ultima_vuelta_cm = distancia_actual_cm
            logging.info(f"Vuelta {self.vueltas}/{self.max_vueltas} completada (distancia: {distancia_recorrida_cm} cm)")
            
            # --- Verificación de Completado de Vueltas ---
            if self.vueltas >= self.max_vueltas:
                logging.info(f"{self.max_vueltas} vueltas completadas.")
                
                # --- Retorno a Sección de Arranque (Regla 9.22) ---
                # Solo aplica en Reto Abierto. En Reto Obstáculos, el estacionamiento ya está en la sección de arranque.
                if self.retorno_arranque_habilitado and self.modo_reto == "abierto":
                    self.retornando_arranque = True
                    # Cálculo de distancia objetivo: distancia_inicial + (3 × perimetro) + distancia_seccion_arranque
                    self.distancia_objetivo_retorno = self.distancia_inicial_cm + (self.max_vueltas * self.perimetro_pista_cm) + self.distancia_seccion_arranque_cm
                    distancia_faltante = self.distancia_objetivo_retorno - distancia_actual_cm
                    logging.info(f"Iniciando retorno a sección de arranque (Reto Abierto). Distancia faltante: {distancia_faltante:.1f} cm")
                    logging.info(f"Distancia objetivo: {self.distancia_objetivo_retorno:.1f} cm")
                else:
                    # --- Detección de Sección de Meta (Regla 9.25.2, Reto Abierto) ---
                    if self.modo_reto == "abierto":
                        self.detectando_meta = True
                        # Cálculo de distancia objetivo: distancia_inicial + (3 × perimetro) + distancia_seccion_meta
                        self.distancia_objetivo_meta = self.distancia_inicial_cm + (self.max_vueltas * self.perimetro_pista_cm) + self.distancia_seccion_meta_cm
                        distancia_faltante = self.distancia_objetivo_meta - distancia_actual_cm
                        logging.info(f"Iniciando búsqueda de sección de meta (Reto Abierto). Distancia faltante: {distancia_faltante:.1f} cm")
                        logging.info(f"Distancia objetivo meta: {self.distancia_objetivo_meta:.1f} cm")
                    else:
                        # --- Comportamiento Original sin Retorno ---
                        if arduino:
                            arduino.enviar_comando(0, recto)
                        if self.modo_reto == "obstaculos":
                            return "ESTACIONAR"
                        else:
                            return "FIN"

        if self.modo_reto == "obstaculos":
            # --- Modo Obstáculos ---
            # Usa detección asíncrona para optimizar rendimiento
            deteccion = vision.obtener_deteccion()
            
            # --- Selección de Estrategia ---
            if self.estrategia:
                vel, ang = self.estrategia.decidir_accion(deteccion, velocidades, angulos, ancho)
            else:
                # --- Lógica por Defecto ---
                color = deteccion["color"]
                cx = deteccion["centroide_x"]
                
                # --- Detección de Violación de Señales (Regla 9.25.5) ---
                # ROJO debe pasar por DERECHA, VERDE por IZQUIERDA
                if self.deteccion_violacion_senales and color in ["ROJO", "VERDE"]:
                    lado = "derecha" if cx > ancho / 2 else "izquierda"
                    lado_correcto = (color == "ROJO" and lado == "derecha") or (color == "VERDE" and lado == "izquierda")
                    
                    if not lado_correcto and color != self.ultima_deteccion_color:
                        self.violaciones_senales += 1
                        logging.warning(f"VIOLACIÓN DE SEÑAL DETECTADA: {color} pasó por {lado} (debería ser {'derecha' if color == 'ROJO' else 'izquierda'})")
                        logging.warning(f"Total de violaciones: {self.violaciones_senales}")
                    
                    self.ultima_deteccion_color = color
                
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
                else:
                    vel = velocidades.get("crucero", 60)
                    ang = recto
            
            # --- Detección de Zona de Estacionamiento ---
            color = deteccion["color"]
            if color == "MAGENTA" and not self.detectando_estacionamiento:
                self.detectando_estacionamiento = True
                self.frames_sin_magenta = 0
                logging.info("Zona de estacionamiento detectada (detección visual).")
            elif color != "MAGENTA" and self.detectando_estacionamiento:
                self.frames_sin_magenta += 1
                if self.frames_sin_magenta > 15:  # ~0.75 segundos sin ver magenta
                    self.detectando_estacionamiento = False

        else:
            # --- Modo Abierto (Muros con LiDAR) ---
            dist = -1.0
            if lidar:
                try:
                    dist = lidar.leer_distancia()
                except Exception as e:
                    logging.error(f"Error al leer distancia del LiDAR: {e}")
                    dist = -1.0
                
            # --- Lógica de Navegación del Reto Abierto ---
            if 0.0 < dist < self.distancia_giro_cm:
                # Evasión/giro en esquina
                vel = velocidades.get("evasion", 40)
                if self.sentido_giro == "horario":
                    ang = angulos.get("evasion_verde", 50)  # Girar a la derecha
                else:
                    ang = angulos.get("evasion_roja", 130)  # Girar a la izquierda
            else:
                # Navegación recta
                vel = velocidades.get("crucero", 60)
                ang = recto

        # --- Envío de Comandos al Arduino ---
        if arduino:
            try:
                arduino.enviar_comando(vel, ang)
            except Exception as e:
                logging.error(f"Error al enviar comando al Arduino: {e}")
        
        # --- Verificación de Sección de Arranque (Regla 9.22, Reto Abierto) ---
        if self.retornando_arranque:
            distancia_faltante = self.distancia_objetivo_retorno - distancia_actual_cm
            if distancia_faltante <= 0:
                logging.info("Sección de arranque alcanzada. Deteniendo vehículo.")
                if arduino:
                    arduino.enviar_comando(0, recto)
                return "FIN"
            # Logging periódico de distancia faltante (cada ~50 cm recorridos)
            elif int(distancia_actual_cm) % 50 == 0:
                logging.info(f"Retornando a sección de arranque (Reto Abierto). Distancia faltante: {distancia_faltante:.1f} cm")
        
        # --- Verificación de Sección de Meta (Regla 9.25.2, Reto Abierto) ---
        if self.detectando_meta:
            distancia_faltante = self.distancia_objetivo_meta - distancia_actual_cm
            if distancia_faltante <= 0:
                logging.info("Sección de meta alcanzada. Deteniendo vehículo (Reto Abierto).")
                if arduino:
                    arduino.enviar_comando(0, recto)
                return "FIN"
            # Logging periódico de distancia faltante (cada ~50 cm recorridos)
            elif int(distancia_actual_cm) % 50 == 0:
                logging.info(f"Buscando sección de meta (Reto Abierto). Distancia faltante: {distancia_faltante:.1f} cm")
            
        # --- Control de Frecuencia del Loop ---
        time.sleep(0.05)
        return "NAVEGACION"

    def exit(self, contexto: dict):
        super().exit(contexto)
        # Detener procesamiento asíncrono de visión al salir del estado
        vision = contexto.get("vision")
        if vision:
            vision.detener_procesamiento_asincrono()