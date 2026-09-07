import logging
import time
import sched
import serial
import cv2
from gpiozero import Button, GPIOZeroError
from src.config import get_hardware, get_competicion, get_velocidades, get_lidar, get_vehiculo, get_vision
from src.config import PID


class Estado:
    """Clase base abstracta para todos los estados del robot."""
    def enter(self, contexto: dict):
        """Se ejecuta al entrar al estado."""
        logging.info(f"Entrando al estado: {self.__class__.__name__}")

    def ejecutar(self, contexto: dict) -> str:
        """Lógica principal del estado. Debe retornar el nombre del siguiente estado."""
        raise NotImplementedError("El método ejecutar() debe ser implementado.")

    def exit(self, contexto: dict):
        """Se ejecuta antes de salir del estado."""
        pass


class MaquinaDeEstados:
    def __init__(self, contexto: dict):
        self.estados = {}
        self.estado_actual = None
        self.contexto = contexto
        # Planificador de tareas de la biblioteca estándar
        self.scheduler = sched.scheduler(time.monotonic, time.sleep)
        self.fsm_rate_hz = 50
        self.period = 1.0 / self.fsm_rate_hz
        self.corriendo = False

    def agregar_estado(self, nombre: str, estado: Estado):
        self.estados[nombre] = estado

    def set_estado_inicial(self, nombre: str):
        if nombre in self.estados:
            self.estado_actual = self.estados[nombre]
            self.estado_actual.enter(self.contexto)
        else:
            logging.error(f"Estado inicial '{nombre}' no registrado.")

    def _tick_ciclo(self):
        """Ejecuta una iteración del ciclo de vida y agenda el siguiente paso."""
        if not self.corriendo or self.estado_actual is None:
            return

        t_inicio = time.monotonic()

        # Ejecutar lógica del estado actual
        siguiente_estado_nombre = self.estado_actual.ejecutar(self.contexto)

        # Condición de salida limpia
        if siguiente_estado_nombre == "SALIR":
            self.estado_actual.exit(self.contexto)
            logging.info("Máquina de estados finalizada.")
            self.corriendo = False
            return

        # Transicionar a otro estado si se solicita
        if siguiente_estado_nombre and siguiente_estado_nombre != self._obtener_nombre_estado(self.estado_actual):
            if siguiente_estado_nombre in self.estados:
                self.estado_actual.exit(self.contexto)
                self.estado_actual = self.estados[siguiente_estado_nombre]
                self.estado_actual.enter(self.contexto)
            else:
                logging.error(f"Se intentó transicionar a un estado desconocido: '{siguiente_estado_nombre}'")

        # Agendar el siguiente ciclo compensando el tiempo de ejecución del tick actual
        t_fin = time.monotonic()
        tiempo_ejecucion = t_fin - t_inicio
        delay_siguiente = max(0.0, self.period - tiempo_ejecucion)
        
        if self.corriendo:
            self.scheduler.enter(delay_siguiente, 1, self._tick_ciclo)

    def run(self):
        """Ciclo de vida principal. Regula la frecuencia utilizando sched."""
        if self.estado_actual is None:
            logging.error("No se ha definido un estado inicial.")
            return

        self.corriendo = True
        # Agendar el primer tick de ejecución inmediata
        self.scheduler.enter(0, 1, self._tick_ciclo)
        
        # Bloquear e iniciar el planificador de eventos
        try:
            self.scheduler.run()
        except KeyboardInterrupt:
            self.corriendo = False
            raise

    def _obtener_nombre_estado(self, estado: Estado) -> str:
        for nombre, est in self.estados.items():
            if est == estado:
                return nombre
        return ""


class EstadoInicio(Estado):
    def __init__(self):
        super().__init__()
        self.boton_inicio = None
        self.estado_anterior_boton = None  # Para detectar cambios de estado (toggle)

    def enter(self, contexto: dict):
        super().enter(contexto)
        logging.info("Inicializando sistemas...")
        
        # --- Configuración del Pulsador de Retención de Inicio ---
        hardware_config = get_hardware()
        pin_boton = hardware_config.get("pin_boton_inicio", 17)
        
        # --- Inicializar Botón GPIO (Regla 9.11) ---
        try:
            self.boton_inicio = Button(pin_boton, pull_up=True)
            self.estado_anterior_boton = self.boton_inicio.is_pressed
            logging.info(f"Pulsador de retención configurado en GPIO {pin_boton}")
            logging.info(f"Estado inicial: {'ON' if not self.estado_anterior_boton else 'OFF'}")
        except (GPIOZeroError, ValueError) as e:
            logging.error(f"Error al inicializar botón GPIO: {e}")
            logging.warning("Usando modo degradado: espera de teclado")
            self.boton_inicio = None
        
        time.sleep(1)  # Espera breve para estabilización del GPIO
        logging.info("Sistemas listos. Esperando cambio en el pulsador de retención...")

    def ejecutar(self, contexto: dict) -> str:
        # --- Esperar Pulsador de Retención Físico (Regla 9.11) ---
        if self.boton_inicio is not None:
            # Detectar cambio de estado (toggle) del switch
            estado_actual = self.boton_inicio.is_pressed
            if estado_actual != self.estado_anterior_boton:
                logging.info(f"Pulsador de retención cambiado de estado. Nuevo estado: {'ON' if not estado_actual else 'OFF'}. Iniciando ronda.")
                self.estado_anterior_boton = estado_actual
                return "NAVEGACION"
            else:
                return "INICIO"  # Mantener en espera
        else:
            # --- Modo Degradado: Entrada por Teclado ---
            logging.warning("Botón GPIO no disponible. Presione ENTER para iniciar...")
            try:
                input()  # Esperar ENTER
                logging.info("Inicio por teclado detectado. Iniciando ronda.")
                return "NAVEGACION"
            except (KeyboardInterrupt, EOFError):
                return "INICIO"

    def exit(self, contexto: dict):
        super().exit(contexto)
        # --- Transferir botón al contexto para reutilizar como parada de emergencia ---
        # No se cierra aquí; el ciclo de vida lo gestiona el contexto global
        if self.boton_inicio is not None:
            contexto["boton_parada"] = self.boton_inicio
            logging.info("Botón transferido al contexto como botón de parada.")
        self.boton_inicio = None


class EstadoNavegacion(Estado):
    @staticmethod
    def _angulo_proporcional(recto: int, destino: int, cx: int, ancho: int) -> int:
        # Ángulo de dirección proporcional: más cerca del centro del frame, mayor giro
        factor = max(0.0, min(1.0, 1.0 - abs(cx - ancho / 2) / (ancho / 2)))
        return int(recto + factor * (destino - recto))

    def _detener_robot_emergencia(self, contexto, motivo):
        """Método centralizado para detención de emergencia."""
        arduino = contexto.get("arduino")
        if arduino:
            arduino.enviar_comando(0, 90)
        logging.warning(f"Detención de emergencia: {motivo}")
        return "FIN"

    def _decidir_movimiento_obstaculos(self, deteccion, velocidades, angulos, ancho, recto):
        """Decide movimiento basado en detección de obstáculos."""
        color = deteccion["color"]
        cx = deteccion["centroide_x"]
        
        estrategia = {
            "ROJO": (velocidades.get("evasion", 40), angulos.get("giro_derecha", 50)),
            "VERDE": (velocidades.get("evasion", 40), angulos.get("giro_izquierda", 130)),
        }
        
        if color in estrategia:
            vel, ang = estrategia[color]
            ang = self._angulo_proporcional(recto, ang, cx, ancho)
            return vel, ang
        return velocidades.get("crucero", 60), recto

    def _obtener_telemetria_segura(self, arduino):
        """Obtiene telemetría con manejo de errores centralizado."""
        try:
            return arduino.obtener_telemetria() if arduino else {}
        except (AttributeError, KeyError) as e:
            logging.error(f"Error al obtener telemetría: {e}")
            return {}

    def _obtener_componentes(self, contexto):
        """Extrae y valida componentes del contexto."""
        return {
            'cap': contexto.get("cap"),
            'vision': contexto.get("vision"),
            'arduino': contexto.get("arduino"),
            'lidar': contexto.get("lidar"),
            'velocidades': contexto.get("velocidades"),
            'angulos': contexto.get("angulos")
        }

    def _ejecutar_auto_deteccion(self, contexto: dict, tiempo_transcurrido: float):
        """Ejecuta la lógica de auto-detección de modo y sentido de giro."""
        if self.auto_detect_modo and not self.modo_detectado:
            self._detectar_modo(contexto, tiempo_transcurrido)
        
        if self.auto_detect_sentido and not self.sentido_detectado:
            self._detectar_sentido(contexto, tiempo_transcurrido)
        
        # Verificar si ambas detecciones están completas
        if (not self.auto_detect_modo or self.modo_detectado) and (not self.auto_detect_sentido or self.sentido_detectado):
            self.deteccion_completada = True
            logging.info(f"Auto-detección completada: Modo={self.modo_reto}, Sentido={self.sentido_giro}")

    def _detectar_modo(self, contexto: dict, tiempo_deteccion: float):
        """Lógica separada para detección de modo de competición."""
        if tiempo_deteccion >= self.modo_deteccion_timeout:
            self.modo_reto = self._determinar_modo_final()
            self.modo_detectado = True
            return
        
        vision = contexto.get("vision")
        if vision:
            deteccion = vision.obtener_deteccion()
            color = deteccion.get("color", "NINGUNO")
            if color in ["ROJO", "VERDE"]:
                self.colores_detectados += 1
                logging.debug(f"Detección de color {color} - Total: {self.colores_detectados}")

    def _determinar_modo_final(self):
        """Determina el modo final basado en detecciones acumuladas."""
        if self.colores_detectados >= self.modo_deteccion_umbral:
            logging.info(f"Auto-detección: MODO OBSTÁCULOS detectado ({self.colores_detectados} colores)")
            return "obstaculos"
        else:
            logging.info(f"Auto-detección: MODO {self.modo_reto_default.upper()} por defecto (colores insuficientes: {self.colores_detectados})")
            return self.modo_reto_default

    def _detectar_sentido(self, contexto: dict, tiempo_deteccion: float):
        """Lógica separada para detección de sentido de giro."""
        if tiempo_deteccion >= self.sentido_deteccion_timeout:
            if not self.sentido_detectado:
                self.sentido_giro = self.sentido_giro_default
                logging.info(f"Auto-detección: SENTIDO {self.sentido_giro.upper()} por defecto (timeout)")
            self.sentido_detectado = True
            return
        
        lidar = contexto.get("lidar")
        if lidar:
            try:
                dist = lidar.leer_distancia()
                if 0.0 < dist < self.sentido_deteccion_distancia:
                    self._analizar_paredes_laterales(lidar)
            except (AttributeError, ValueError) as e:
                logging.error(f"Error en auto-detección de sentido: {e}")

    def _analizar_paredes_laterales(self, lidar):
        """Analiza paredes laterales para determinar sentido de giro."""
        logging.info("Auto-detección: Esquina detectada, analizando paredes laterales...")
        
        # Escanear lado derecho
        lidar.apuntar_servo(45)
        time.sleep(0.3)
        dist_derecha = lidar.leer_distancia()
        
        # Escanear lado izquierdo
        lidar.apuntar_servo(135)
        time.sleep(0.3)
        dist_izquierda = lidar.leer_distancia()
        
        # Volver al centro
        lidar.apuntar_servo(90)
        
        # Determinar sentido basado en qué pared está más cerca
        if dist_derecha > 0 and dist_izquierda > 0:
            if dist_derecha < dist_izquierda:
                self.sentido_giro = "horario"
                logging.info(f"Auto-detección: SENTIDO HORARIO detectado (derecha: {dist_derecha:.1f}cm, izquierda: {dist_izquierda:.1f}cm)")
            else:
                self.sentido_giro = "antihorario"
                logging.info(f"Auto-detección: SENTIDO ANTIHORARIO detectado (derecha: {dist_derecha:.1f}cm, izquierda: {dist_izquierda:.1f}cm)")
            self.sentido_detectado = True

    def enter(self, contexto: dict):
        super().enter(contexto)
        logging.info("Modo navegación autónoma iniciado.")

        # Configuración de competición
        comp_config = get_competicion()
        velocidades_config = get_velocidades()
        self.modo_reto = comp_config.get("modo_reto", "obstaculos")
        self.sentido_giro = comp_config.get("sentido_giro", "horario")
        self.max_vueltas = comp_config.get("max_vueltas", 3)
        self.tiempo_limite_segundos = comp_config.get("tiempo_limite_segundos", 180)  # C-3: asignado aqui
        self.deteccion_violacion_senales = comp_config.get("deteccion_violacion_senales", True)  # Regla 9.25.5

        # ==================== AUTO-DETECCIÓN ====================
        self.auto_detect_modo = comp_config.get("auto_detect_modo", True)
        self.modo_deteccion_timeout = comp_config.get("modo_deteccion_timeout_seg", 10)
        self.modo_deteccion_umbral = comp_config.get("modo_deteccion_umbral_colores", 5)
        self.modo_reto_default = comp_config.get("modo_reto_default", "abierto")
        
        self.auto_detect_sentido = comp_config.get("auto_detect_sentido", True)
        self.sentido_deteccion_distancia = comp_config.get("sentido_deteccion_distancia_cm", 70)
        self.sentido_deteccion_timeout = comp_config.get("sentido_deteccion_timeout_seg", 15)
        self.sentido_giro_default = comp_config.get("sentido_giro_default", "horario")
        
        # Variables de estado para auto-detección
        self.modo_detectado = False
        self.sentido_detectado = False
        self.colores_detectados = 0  # Contador de detecciones rojo/verde
        self.tiempo_inicio_deteccion = time.time()
        self.deteccion_completada = False

        lidar_config = get_lidar()
        self.distancia_giro_cm = lidar_config.get("distancia_giro_cm", 50.0)

        # Configuración del vehículo para verificación de espacio lateral
        vehiculo_config = get_vehiculo()
        self.ancho_max_cm = max(vehiculo_config.get("ancho_frente_cm", 15.0), vehiculo_config.get("ancho_atras_cm", 17.0))
        self.radio_giro_cm = vehiculo_config.get("radio_giro_cm", 8.5)
        # Espacio mínimo lateral: ancho máximo + radio de giro + margen de seguridad (5cm)
        self.espacio_lateral_minimo_cm = self.ancho_max_cm + self.radio_giro_cm + 5.0  # ~30.5cm

        # Odometría visual: flag opt-in (se puede alternar en config.py sin tocar código)
        vision_config = get_vision()
        self.odometria_visual_habilitada = vision_config.get("odometria_visual_habilitada", True)
        if self.odometria_visual_habilitada:
            logging.info("Odometría visual HABILITADA — control de velocidad vía PID.")
        else:
            logging.info("Odometría visual DESHABILITADA — usando PWM fijo de config.py.")

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

        # Obtener ancho del frame desde cámara USB (cv2.VideoCapture)
        cap = contexto.get("cap")
        if cap:
            self.ancho = int(cap.get(cv2.CAP_PROP_FRAME_WIDTH))
        else:
            vision_config = get_vision()
            self.ancho = vision_config.get("width", 640)

        # Procesamiento asíncrono de visión
        vision = contexto.get("vision")
        cap = contexto.get("cap")
        if vision and cap:
            vision.iniciar_procesamiento_asincrono(cap)

    def ejecutar(self, contexto: dict) -> str:
        # Verificación de botón de parada de emergencia (switch)
        if self.boton_parada and self.boton_parada.is_pressed:
            return self._detener_robot_emergencia(contexto, "Botón de parada presionado")

        # Verificación de límite de tiempo (Regla 9.25.1)
        tiempo_transcurrido = time.time() - self.tiempo_inicio_ronda
        if tiempo_transcurrido > self.tiempo_limite_segundos:
            return self._detener_robot_emergencia(contexto, f"Tiempo límite agotado ({tiempo_transcurrido:.1f}s > {self.tiempo_limite_segundos}s)")

        # ==================== LÓGICA DE AUTO-DETECCIÓN ====================
        if not self.deteccion_completada:
            self._ejecutar_auto_deteccion(contexto, tiempo_transcurrido)

        # Extraer componentes del contexto
        componentes = self._obtener_componentes(contexto)
        cap = componentes['cap']
        vision = componentes['vision']
        arduino = componentes['arduino']
        lidar = componentes['lidar']
        velocidades = componentes['velocidades']
        angulos = componentes['angulos']

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
        telemetria = self._obtener_telemetria_segura(arduino)
        z_acumulado = telemetria.get("z", 0)

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
                    return self._detener_robot_emergencia(contexto, "Completado de vueltas (Reto Abierto)")

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
            vel, ang = self._decidir_movimiento_obstaculos(deteccion, velocidades, angulos, ancho, recto)

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


class EstadoEstacionar(Estado):
    def enter(self, contexto: dict):
        super().enter(contexto)
        logging.info("Maniobra de estacionamiento iniciada.")
        
        # Activar visión para detección de área MAGENTA
        vision = contexto.get("vision")
        cap = contexto.get("cap")
        if vision and cap:
            vision.iniciar_procesamiento_asincrono(cap)
            logging.info("Visión activada para detección de área MAGENTA en estacionamiento")
        
        # Configuración del LiDAR
        lidar_config = get_lidar()
        self.umbral_hueco_cm = lidar_config.get("umbral_hueco_cm", 55.0)
        self.distancia_pared_cm = lidar_config.get("distancia_pared_cm", 40.0)
        self.angulo_inicio = lidar_config.get("angulo_escaneo_inicio", 45)
        self.angulo_fin = lidar_config.get("angulo_escaneo_fin", 135)
        self.paso = lidar_config.get("paso_escaneo", 15)
        
        # Configuración del vehículo
        vehiculo_config = get_vehiculo()
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
            return self._fase_escaneo(lidar, arduino, contexto)
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
    
    def _fase_escaneo(self, lidar, arduino, contexto):
        """Escanea el entorno buscando un hueco para estacionamiento usando LiDAR + cámara."""
        logging.info("Fase: Escaneo de hueco de estacionamiento (LiDAR + Cámara).")
        
        # Detener Robot para Escaneo
        self._mover(arduino, 0, self.recto, 0.5, "detener robot para escaneo")
        
        # Escanear Entorno con LiDAR
        try:
            mapa = lidar.escanear_entorno(self.angulo_inicio, self.angulo_fin, self.paso)
            logging.info(f"Mapa LiDAR: {mapa}")
        except (AttributeError, ValueError) as e:
            logging.error(f"Error al escanear entorno con LiDAR: {e}")
            mapa = []
        
        # Verificar detección de MAGENTA con cámara
        vision = contexto.get("vision")
        magenta_detectado = False
        area_magenta = 0
        
        if vision:
            try:
                deteccion = vision.obtener_deteccion()
                if deteccion.get("color") == "MAGENTA":
                    magenta_detectado = True
                    area_magenta = deteccion.get("area", 0)
                    logging.info(f"Área MAGENTA detectada (área: {area_magenta})")
            except (AttributeError, KeyError) as e:
                logging.error(f"Error al obtener detección de visión: {e}")
        
        # Buscar Hueco de Estacionamiento con LiDAR
        # Hueco detectado: 3 lecturas consecutivas con distancia > umbral
        hueco_encontrado = False
        angulo_hueco = None
        
        for i in range(len(mapa) - 2):
            _, dist1 = mapa[i]
            ang2, dist2 = mapa[i + 1]
            _, dist3 = mapa[i + 2]
            if (dist1 > self.umbral_hueco_cm and
                dist2 > self.umbral_hueco_cm and
                dist3 > self.umbral_hueco_cm):
                hueco_encontrado = True
                angulo_hueco = ang2
                logging.info(f"Hueco LiDAR detectado en ángulo {ang2}°")
                break
        
        # Validación combinada: Requiere hueco LiDAR Y área MAGENTA
        hueco_valido = hueco_encontrado and magenta_detectado
        
        if hueco_valido:
            self.fase = "aproximacion"
            self.tiempo_inicio_fase = time.time()
            logging.info(f"Hueco validado (LiDAR: {angulo_hueco}° + MAGENTA: área {area_magenta}). Iniciando aproximación.")
        elif hueco_encontrado and not magenta_detectado:
            # Hueco encontrado pero sin área MAGENTA - no es el estacionamiento correcto
            logging.warning("Hueco LiDAR detectado pero sin área MAGENTA - Continuando búsqueda")
            self.intentos_escaneo += 1
            if self.intentos_escaneo >= self.max_intentos_escaneo:
                logging.warning("No se encontró hueco válido después de varios intentos. Abortando.")
                return "FIN"
            logging.info(f"Intento {self.intentos_escaneo}/{self.max_intentos_escaneo} - Avanzando para reintentar")
            self._mover(arduino, self.vel_lenta, self.recto, 1.0, "avanzar para reintentar escaneo")
        else:
            # No hay hueco
            self.intentos_escaneo += 1
            if self.intentos_escaneo >= self.max_intentos_escaneo:
                logging.warning("No se encontró hueco después de varios intentos. Abortando.")
                return "FIN"
            logging.info(f"No se encontró hueco. Intento {self.intentos_escaneo}/{self.max_intentos_escaneo}")
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
        
        telemetria_inicial = self._obtener_telemetria_segura(arduino)
        z_inicial = telemetria_inicial.get("z", 0)
        
        # Timeout de seguridad por paso (evita bloqueo infinito si el sensor falla)
        TIMEOUT_PASO_S = 5.0
        
        # Paso 1: Girar ruedas para reversa en ángulo
        logging.info("Reversa paso 1: Girar a la derecha")
        self._mover(arduino, self.vel_reversa, self.evasion_der, 0, "girar para reversa")
        t_paso = time.time()
        while True:
            telemetria = self._obtener_telemetria_segura(arduino)
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
            telemetria = self._obtener_telemetria_segura(arduino)
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
            telemetria = self._obtener_telemetria_segura(arduino)
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
        telemetria = self._obtener_telemetria_segura(arduino)
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
        
        # Desactivar visión al salir del estado
        vision = contexto.get("vision")
        if vision:
            vision.detener_procesamiento_asincrono()
            logging.info("Visión desactivada al salir de estacionamiento")
        
        # Asegurar Detención del Robot
        arduino = contexto.get("arduino")
        if arduino:
            self._mover(arduino, 0, 90, 0, "detener robot al salir de estacionamiento")


class EstadoFin(Estado):
    def enter(self, contexto: dict):
        super().enter(contexto)
        logging.info("Secuencia de finalización activada.")

    def ejecutar(self, contexto: dict) -> str:
        arduino = contexto.get("arduino")
        angulos = contexto.get("angulos", {})
        
        # --- Detener Motores y Centrar Servo ---
        try:
            if arduino and arduino.esta_conectado():
                arduino.enviar_comando(0, angulos.get("recto", 90))
        except (serial.SerialException, AttributeError) as e:
            logging.error(f"Error al enviar comando de detención: {e}")
            
        logging.info("Motores detenidos. Carrera finalizada.")
        
        # --- Salir de la FSM ---
        return "SALIR"

    def exit(self, contexto: dict):
        super().exit(contexto)
