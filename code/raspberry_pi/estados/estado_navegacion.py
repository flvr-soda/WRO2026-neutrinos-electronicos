import time
import logging
import cv2
import serial
from .fsm import Estado
from src.pid import PID

class EstadoNavegacion(Estado):
    @staticmethod
    def _angulo_proporcional(recto: int, destino: int, cx: int, ancho: int) -> int:
        # Ángulo de dirección proporcional: más cerca del centro del frame, mayor giro
        factor = max(0.0, min(1.0, 1.0 - abs(cx - ancho / 2) / (ancho / 2)))
        return int(recto + factor * (destino - recto))

    def enter(self, contexto: dict):
        super().enter(contexto)
        logging.info("Modo navegación autónoma iniciado.")

        # Configuración de competición
        config_loader = contexto.get("config_loader")
        comp_config = config_loader.get_competicion()
        velocidades_config = config_loader.get_velocidades()
        self.modo_reto = comp_config.get("modo_reto", "obstaculos")
        self.sentido_giro = comp_config.get("sentido_giro", "horario")
        self.max_vueltas = comp_config.get("max_vueltas", 3)
        self.tiempo_limite_segundos = comp_config.get("tiempo_limite_segundos", 180)  # C-3: asignado aqui
        self.deteccion_violacion_senales = comp_config.get("deteccion_violacion_senales", True)  # Regla 9.25.5

        lidar_config = config_loader.get_lidar()
        self.distancia_giro_cm = lidar_config.get("distancia_giro_cm", 50.0)

        # Configuración del vehículo para verificación de espacio lateral
        vehiculo_config = config_loader.get_vehiculo()
        self.ancho_max_cm = max(vehiculo_config.get("ancho_frente_cm", 15.0), vehiculo_config.get("ancho_atras_cm", 17.0))
        self.radio_giro_cm = vehiculo_config.get("radio_giro_cm", 8.5)
        # Espacio mínimo lateral: ancho máximo + radio de giro + margen de seguridad (5cm)
        self.espacio_lateral_minimo_cm = self.ancho_max_cm + self.radio_giro_cm + 5.0  # ~30.5cm

        # Odometría visual: flag opt-in (se puede alternar en config.yaml sin tocar código)
        vision_config = config_loader.get_vision()
        self.odometria_visual_habilitada = vision_config.get("odometria_visual_habilitada", True)
        if self.odometria_visual_habilitada:
            logging.info("Odometría visual HABILITADA — control de velocidad vía PID.")
        else:
            logging.info("Odometría visual DESHABILITADA — usando PWM fijo de config.yaml.")

        # PID de velocidad (lazo cerrado por odometría visual)
        pid_config = vision_config.get("pid", {})
        self.pid_velocidad = PID(
            kp=pid_config.get("kp", 1.2),
            ki=pid_config.get("ki", 0.3),
            kd=pid_config.get("kd", 0.05),
            output_min=0,
            output_max=100,
            integral_max=pid_config.get("integral_max", 50.0)  # A-3: anti-windup
        )
        self.velocidad_objetivo_crucero = velocidades_config.get("crucero_cm_s", 30.0)  # cm/s
        self.velocidad_objetivo_evasion = velocidades_config.get("evasion_cm_s", 20.0)  # cm/s

        # Variables de estado para conteo de vueltas
        self.vueltas = 0

        # Variables para búsqueda de estacionamiento (Reto Obstáculos)
        self.buscando_estacionamiento = False
        self.tiempo_inicio_busqueda_estacionamiento = 0
        self.timeout_busqueda_estacionamiento_segundos = 30  # 30 segundos de timeout

        # Variables para detección de violación de señales (Regla 9.25.5)
        self.violaciones_senales = 0
        self.ultima_deteccion_color = None

        # Ancho del frame (se cachea en la primera iteración)
        self.ancho = None

        # Botón de parada de emergencia: recibir referencia desde contexto
        # (evita re-crear Button sobre el mismo GPIO con switch de enclavamiento)
        self.boton_parada = contexto.get("boton_parada", None)
        if self.boton_parada:
            logging.info("Botón de parada recibido desde contexto.")
        else:
            logging.warning("Botón de parada no disponible en contexto.")

        # Inicio de ronda (Regla 9.25.1)
        self.tiempo_inicio_ronda = time.time()
        logging.info(f"Límite de tiempo: {self.tiempo_limite_segundos} segundos")

        # Obtener ancho del frame desde configuración (picamera2 no usa cap.get())
        vision_config = config_loader.get_vision()
        self.ancho = vision_config.get("width", 640)

        # Procesamiento asíncrono de visión
        vision = contexto.get("vision")
        cap = contexto.get("cap")
        if vision and cap:
            vision.iniciar_procesamiento_asincrono(cap)

    def ejecutar(self, contexto: dict) -> str:
        # Verificación de botón de parada de emergencia (switch)
        if self.boton_parada and self.boton_parada.is_pressed:
            logging.warning("Botón de parada presionado. Deteniendo robot.")
            arduino = contexto.get("arduino")
            if arduino:
                arduino.enviar_comando(0, 90)
            return "FIN"

        # Verificación de límite de tiempo (Regla 9.25.1)
        tiempo_transcurrido = time.time() - self.tiempo_inicio_ronda
        if tiempo_transcurrido > self.tiempo_limite_segundos:
            logging.warning(f"Tiempo límite agotado ({tiempo_transcurrido:.1f}s > {self.tiempo_limite_segundos}s)")
            arduino = contexto.get("arduino")
            if arduino:
                arduino.enviar_comando(0, 90)
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

        # self.ancho se cachea en enter() desde configuración — sin cap.read() en el loop (C-4)
        if self.ancho is None:
            logging.warning("Ancho de frame no disponible. Reintentando en próxima iteración.")
            return "NAVEGACION"


        ancho = self.ancho
        recto = angulos.get("recto", 90)

        # Telemetría del MPU6050
        try:
            telemetria = arduino.obtener_telemetria() if arduino else {}
            z_acumulado = telemetria.get("z", 0)
        except (AttributeError, KeyError) as e:
            logging.error(f"Error al obtener telemetría del Arduino: {e}")
            telemetria = {}
            z_acumulado = 0

        # Cálculo de vueltas
        vueltas_completas = int(abs(z_acumulado) / 360.0)

        # Detección de nueva vuelta
        if vueltas_completas > self.vueltas:
            self.vueltas = vueltas_completas
            logging.info(f"Vuelta {self.vueltas}/{self.max_vueltas} completada (Z: {z_acumulado:.1f} grados)")

            # Iniciar búsqueda de estacionamiento al completar las vueltas (Reto Obstáculos)
            if self.vueltas >= self.max_vueltas and self.modo_reto == "obstaculos":
                self.buscando_estacionamiento = True
                self.tiempo_inicio_busqueda_estacionamiento = time.time()
                logging.info(f"Iniciando búsqueda visual de estacionamiento (color MAGENTA).")

            # Verificación de completado de vueltas
            if self.vueltas >= self.max_vueltas:
                logging.info(f"{self.max_vueltas} vueltas completadas.")

                if self.modo_reto == "abierto":
                    logging.info("Deteniendo vehículo (Reto Abierto).")
                    if arduino:
                        arduino.enviar_comando(0, recto)
                    return "FIN"

        if self.modo_reto == "obstaculos":
            # Modo obstáculos (detección asíncrona)
            deteccion = vision.obtener_deteccion()
            color = deteccion["color"]
            cx = deteccion["centroide_x"]

            # Detección de violación de señales (Regla 9.25.5)
            # A-1: solo evaluar si la detección es válida (area > 0 y centroide no es (0,0) por defecto)
            if (self.deteccion_violacion_senales
                    and color in ["ROJO", "VERDE"]
                    and deteccion.get("area", 0) > 0):
                lado = "derecha" if cx > ancho / 2 else "izquierda"
                lado_correcto = (color == "ROJO" and lado == "derecha") or (color == "VERDE" and lado == "izquierda")
                if not lado_correcto and color != self.ultima_deteccion_color:
                    self.violaciones_senales += 1
                    logging.warning(f"VIOLACIÓN DE SEÑAL DETECTADA: {color} pasó por {lado} (debería ser {'derecha' if color == 'ROJO' else 'izquierda'})")
                    logging.warning(f"Total de violaciones: {self.violaciones_senales}")
                self.ultima_deteccion_color = color

            # Decisión de movimiento (Regla 9.19: ROJO→derecha, VERDE→izquierda)
            if color == "ROJO":
                # Regla 9.19: ROJO -> mantenerse a la DERECHA
                vel = velocidades.get("evasion", 40)
                ang = self._angulo_proporcional(recto, angulos.get("giro_derecha", 50), cx, ancho)
            elif color == "VERDE":
                # Regla 9.19: VERDE -> mantenerse a la IZQUIERDA
                vel = velocidades.get("evasion", 40)
                ang = self._angulo_proporcional(recto, angulos.get("giro_izquierda", 130), cx, ancho)
            else:
                # MAGENTA o NINGUNO: avanzar recto a velocidad crucero
                vel = velocidades.get("crucero", 60)
                ang = recto

        else:
            # Modo abierto (muros con LiDAR)
            dist = -1.0
            if lidar:
                try:
                    dist = lidar.leer_distancia()
                except (AttributeError, ValueError) as e:
                    logging.error(f"Error al leer distancia del LiDAR: {e}")
                    dist = -1.0

            # Lógica de navegación del reto abierto
            if 0.0 < dist < self.distancia_giro_cm:
                # Verificar espacio lateral antes de girar
                espacio_lateral_suficiente = True
                if lidar:
                    try:
                        # Escanear al extremo del rango para verificar espacio lateral
                        angulo_verificacion = 45 if self.sentido_giro == "horario" else 135
                        lidar.apuntar_servo(angulo_verificacion)
                        time.sleep(0.2)  # Esperar estabilización del servo
                        dist_lateral = lidar.leer_distancia()
                        lidar.apuntar_servo(90)  # Volver al centro
                        
                        if dist_lateral > 0 and dist_lateral < self.espacio_lateral_minimo_cm:
                            espacio_lateral_suficiente = False
                            logging.warning(f"Espacio lateral insuficiente ({dist_lateral:.1f}cm < {self.espacio_lateral_minimo_cm:.1f}cm). Continuando recto.")
                    except (AttributeError, ValueError) as e:
                        logging.error(f"Error al verificar espacio lateral: {e}")
                
                if espacio_lateral_suficiente:
                    # Evasión/giro en esquina
                    vel = velocidades.get("evasion", 40)
                    if self.sentido_giro == "horario":
                        ang = angulos.get("giro_derecha", 50)  # Girar a la derecha
                    else:
                        ang = angulos.get("giro_izquierda", 130)  # Girar a la izquierda
                else:
                    # Espacio lateral insuficiente: continuar recto más lento
                    vel = velocidades.get("evasion", 40)
                    ang = recto
            else:
                # Navegación recta
                vel = velocidades.get("crucero", 60)
                ang = recto

        # Lazo cerrado PID: ajustar PWM con odometría visual si está habilitada
        if self.odometria_visual_habilitada:
            v_actual = vision.obtener_velocidad() if vision else 0.0

            if vel == velocidades.get("crucero", 60):
                self.pid_velocidad.set_setpoint(self.velocidad_objetivo_crucero)
            else:
                self.pid_velocidad.set_setpoint(self.velocidad_objetivo_evasion)

            vel_final = int(self.pid_velocidad.compute(v_actual))
        else:
            # Odometría visual desactivada: usar PWM fijo directamente
            vel_final = vel

        # Envío de comandos al Arduino (con PWM corregido por PID o fijo)
        if arduino:
            try:
                arduino.enviar_comando(vel_final, ang)
            except (AttributeError, serial.SerialException) as e:
                logging.error(f"Error al enviar comando al Arduino: {e}")

        # Verificación de área de estacionamiento (Reto Obstáculos)
        if self.buscando_estacionamiento:
            # Reutilizar la detección ya obtenida en este tick (M-3: evita doble lectura)
            if self.modo_reto == "obstaculos":
                if deteccion["color"] == "MAGENTA":
                    logging.info("Sección de estacionamiento (MAGENTA) detectada. Transicionando a ESTACIONAR.")
                    if arduino:
                        arduino.enviar_comando(0, recto)
                    return "ESTACIONAR"

            # Verificación de timeout de búsqueda
            tiempo_busqueda = time.time() - self.tiempo_inicio_busqueda_estacionamiento
            if tiempo_busqueda > self.timeout_busqueda_estacionamiento_segundos:
                logging.warning(f"Timeout de búsqueda de estacionamiento ({tiempo_busqueda:.1f}s > {self.timeout_busqueda_estacionamiento_segundos}s). Forzando estacionamiento.")
                if arduino:
                    arduino.enviar_comando(0, recto)
                return "ESTACIONAR"

        # M-3: eliminado time.sleep(0.05) — el rate limiting lo maneja la FSM (fsm.py:42)
        return "NAVEGACION"

    def exit(self, contexto: dict):
        super().exit(contexto)
        # Detener procesamiento asíncrono de visión al salir del estado
        vision = contexto.get("vision")
        if vision:
            vision.detener_procesamiento_asincrono()
        # No cerrar botón de parada: es propiedad del contexto, no de este estado
        self.boton_parada = None