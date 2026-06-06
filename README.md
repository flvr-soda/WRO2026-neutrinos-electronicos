# Neutrinos Electrónicos WRO 2026

## Tabla de contenidos

- [Neutrinos Electrónicos WRO 2026](#neutrinos-electrónicos-wro-2026)
  - [Tabla de contenidos](#tabla-de-contenidos)
  - [Introducción del equipo](#introducción-del-equipo)
  - [Descripción del proyecto](#descripción-del-proyecto)
  - [Hardware Usado (19/03/2026)](#hardware-usado-19032026)
    - [Principal](#principal)
    - [Arquitectura de Potencia](#arquitectura-de-potencia)
    - [Sensores](#sensores)
    - [Actuadores](#actuadores)
    - [Otros](#otros)
  - [Software y librerias](#software-y-librerias)
    - [Lenguajes](#lenguajes)
    - [Librerias](#librerias)
  - [Diagramas](#diagramas)
    - [Diagrama de flujo](#diagrama-de-flujo)
    - [Directorios](#directorios)
  - [Lógica Algorítmica](#lógica-algorítmica)
    - [Máquina de Estados Finitos (FSM)](#máquina-de-estados-finitos-fsm)
    - [Sistema de Control PID](#sistema-de-control-pid)
    - [Procesamiento de Visión por Computadora](#procesamiento-de-visión-por-computadora)
    - [Estacionamiento Basado en LiDAR](#estacionamiento-basado-en-lidar)
    - [Protocolo de Comunicación Serial](#protocolo-de-comunicación-serial)
  - [Descripción de Módulos](#descripción-de-módulos)
  - [Desafios de la competición](#desafios-de-la-competición)

## Introducción del equipo

<img src="docs/misc/team.jpeg" alt="Foto del equipo" width="500" align="center">

| Nombre| Rol |
| :--- | :--- |
|Ismael Armada|Programador|
|Sebastián Vera|Mecánico|
|Andrés Lugo|Electricista|
Ismael Armada: tengo 20 años, curso el 4to semestre de mi carrera y soy estudiante de computación. conocí la WRO gracias a un amigo en común que tengo con la coach de nuestro equipo. Con esta competición tan solo planeo desafiarme a mi mismo como programador saltando de lleno, y por primera vez, en el desarrollo de un proyecto importante de ingeniería robótica.
Sebastián Vera: tengo 18 años y soy estudiante de ingeniería mecánica, curso el 2do con 3er semestre. conocí la WRO gracias a mí liceo, ya que en el último año lo pudimos representar. esa experiencia me encantó y me mostró este increíble mundo de la robótica y lo divertido y complicado que es! espero tener la oportunidad de representar tanto a mí equipo como a mi país en esta competencia tan increíble.
Andrés Lugo: tengo 19 años y soy estudiante de ingeniería eléctrica, curso el 2do semestre de ingeniería mecánica. Conocí la WRO por competir junto a Sebastían por primera vez en el último año de liceo. No tenia muchos conocimientos pero fue mi inicio en este mundo, donde espero tener el honor de representar a mi pais.

## Descripción del proyecto

- Paradigma Seleccionado (Cerebro + Sistema Nervioso): Se descarta (POR AHORA) el uso de múltiples Arduinos para evitar problemas de latencia crítica en la transmisión de datos. Se mantiene un sistema híbrido centralizado: Raspberry Pi 4 como nodo maestro de alta velocidad y Arduino UNO como controlador dedicado de hardware en tiempo real.
- Aislamiento del Lazo de Control (PID): La lectura del encoder de cuadratura (100 líneas) y el control de potencia del motor DC (Puente H BTS7960) coexistirán en el mismo Arduino UNO. Esto garantiza un control de velocidad inmediato, fluido y sin retrasos de red.
- Flexibilidad ante "Reglas Sorpresa": Toda la lógica de la competición se desacopla del código fuente mediante un archivo de configuración centralizado (config.yaml). Modificaciones de última hora en los pits (sentido de giro, lado del estacionamiento, colores) se realizarán editando parámetros de texto plano, sin necesidad de reprogramar ni recompilar código.
- Modularidad de Software: En la Raspberry Pi se implementa una Máquina de Estados Finitos (FSM) basada en eventos, lo que facilita el desarrollo, testeo y depuración independiente de cada fase de la carrera (Inicio, Navegación, Esquiva, Estacionamiento).

## Hardware Usado (19/03/2026)

### Principal
- (SBC)  Raspberry Pi 4 Model B - 4GB
- (SBM) Arduino UNO

### Arquitectura de Potencia
- Bateria para motores
- Baterias para Arduino y Raspberry
- Estabilizador de voltaje Modelo XL4015
- Cargador
- Estructura para instalación de baterias
- Dos interruptores (encendido y apagado del vehiculo y el start)
- Fan 5V (Para Raspberry Pi 4)

### Sensores
- Cámara OV5647 de 120°
- Sensores de distancia (HC SR04)
- Sensor de orientación MPU 6050 6° de libertad
- LiDAR TF-Luna sobre servo sg90
- Modulo sensor de velocidad encoder de 100 líneqas (fase desplazada):
  Genera señales de cuadratura para medir velocidad y detectar dirección de giro

### Actuadores
- Puente H MODELO BTS7960
- MOTOR DC
- SERVOMOTOR DE DIRECCIÓN (MG996R) 180°

### Otros
- Cables/Cable USB
- Estaño
- Impresiones 3D

## Software y librerias

### Lenguajes
- Python
- C++ 

### Librerias
- Pyyaml
- OpenCV
- Pyserial

## Diagramas

### Diagrama de flujo

<pre>
                ---------------------------------------------------------
                |                                                       |
                              RASPBERRY PI 4 (Python) 

                [Cámara OV5647] ---> (Procesamiento OpenCV / Filtros HSV)
                                            |
                                            v
                [LiDAR TF-Luna] ---> (Mapeo de Distancia Lateral para Parking) 
                                            |
                                            v
                              (Máquina de Estados Finitos) 
                                Config: Carga config.yaml  
                |                                                       | 
                ---------------------------------------------------------
                                            |
                                            |
                                  Comandos Serial (USB)
                        [Velocidad Crucero, Ángulo Servo Dirección]
                                            |
                                            |
                                            v
                ---------------------------------------------------------
                |                                                       |
                                    ARDUINO UNO (C++) 
                                    
        (Recibe Comandos Serial) ---> [Control PID] <--- [Encoder 100 Lín.]
                                            |
                                            v
                          ------------------+----------------
                          |                                 |
                          v                                 v
                  [Puente H BTS7960]                  [Servo MG996R] 
                  (Motor Tracción)                    (Dirección)

                  *Sensor de Respaldo Seguridad: HC-SR04 / MPU6050

                |                                                       | 
                ---------------------------------------------------------
</pre>

### Directorios

<pre>
  WRO2026-neutrinos-electronicos/
  │
  ├── README.md                         # Documentación principal del equipo
  ├── .gitignore                        # Exclusión de archivos binarios/temporales
  │
  ├── docs/                   	        # Repositorio de recursos de hardware
  │   ├── diagramas_electricos/         # Planos de potencia y sensores (para Andrés)
  │   ├──  modelos_3d/         		# Piezas STL y chasis del vehículo (para Sebastián)
  │   └── misc/         		# Fotos del equipo, robot, etc.
  │
  ├── arduino/                		# Código fuente C++ (Arduino IDE)
  │   └── firmware_terreneitor/
  │   	├── firmware_terreneitor.ino    # Ciclo principal (Setup y Loop)
  │   	├── config.h                    # Asignación estática de Pines e Interrupciones
  │   	├── motores.cpp     	        # Control de puente H, servo MG996R y control PID de velocidad
  │   	├── sensores.cpp                # Rutinas para Encoder, HC-SR04 y MPU6050
  │   	├── comunicacion.cpp	        # Parsers para el protocolo de mensajería Serial
  │   	├── pid.cpp                     # Implementación del controlador PID con anti-windup
  │   	└── pid.h                       # Declaración de la estructura PID y funciones
  │
  └── raspberry_pi/                     # Código fuente Python (Procesamiento Principal)
    ├── requirements.txt                # Librerías necesarias (opencv-python, pyyaml, pyserial, gpiozero)
    ├── main.py                         # Script de arranque y orquestación del sistema
    ├── config.yaml                     # Parámetros de calibración y variables de competición
    ├──  src/                            # Módulos y librerías de control
    | ├── __init__.py
    | ├── config_loader.py		# Validador y lector del archivo YAML
    | ├── comms_arduino.py	        # Interfaz de comunicación Serial
    | ├── vision.py                     # Algoritmos de segmentación HSV (Cámara 120°)
    | └── lidar.py                      # Control del servo SG90 y lecturas del TF-Luna
    |
    ├──  estados/        	        # Clases independientes de la Máquina de Estados
    |  ├── __init__.py
    |  ├── fsm.py      		        # Controlador nativo de transiciones
    |  ├── estado_inicio.py              # Rutina de espera y lectura de condiciones iniciales
    |  ├── estado_navegacion.py 	        # Algoritmo de evasión de obstáculos (Rojo/Verde)
    |  ├── estado_estacionar.py          # Maniobra automática de parqueo en paralelo
    |  └── estado_fin.py                 # Detención segura del vehículo al cerrar la ronda
    |
    └── estrategias/                    # Estrategias intercambiables para regla sorpresa
      ├── __init__.py
      ├── estrategia_base.py            # Clase base abstracta para estrategias
      └── estrategia_normal.py          # Estrategia normal de navegación
</pre>

## Lógica Algorítmica

### Máquina de Estados Finitos (FSM)

El comportamiento del robot está controlado por una Máquina de Estados Finitos basada en eventos implementada en Python en la Raspberry Pi. La FSM gestiona el ciclo completo de la carrera a través de estados distintos:

**Estado: INICIO**
- Espera el presionado del botón de inicio físico vía GPIO
- Inicializa todas las interfaces de hardware (cámara, LiDAR, comunicación Arduino)
- Carga la configuración de competición desde config.yaml
- Modo degradado con entrada por teclado si GPIO no disponible
- Transiciona a NAVEGACION al presionar el botón

**Estado: NAVEGACION**
- Estado principal de navegación para ambos retos (Obstáculos y Abierto)
- Implementa conteo de vueltas usando telemetría del encoder
- Cumple el límite de tiempo de 3 minutos
- Detecta sección de meta para Reto Abierto
- Detecta violaciones de señales para Reto Obstáculos
- Retorna a sección de arranque después de 3 vueltas en Reto Abierto
- Usa procesamiento asíncrono de visión para detección de obstáculos
- Transiciona a ESTACIONAR (Obstáculos) o FIN (Abierto) según tipo de reto

**Estado: ESTACIONAR**
- Ejecuta maniobra automática de estacionamiento en paralelo usando LiDAR
- Algoritmo de estacionamiento multifase:
  1. **Fase de Escaneo:** Barre el servo LiDAR para detectar hueco de estacionamiento
  2. **Fase de Aproximación:** Avanza y se alinea con el hueco detectado
  3. **Fase de Reversa:** Ejecuta maniobra de reversa dentro del espacio
  4. **Fase de Enderezar:** Ajusta posición final dentro del espacio
- Usa sensor de distancia TF-Luna para detección de hueco
- Transiciona a FIN al completar

**Estado: FIN**
- Detiene todos los motores inmediatamente
- Centra el servo de dirección
- Señala salida de FSM
- Asegura apagado seguro de todo el hardware

### Sistema de Control PID

El Arduino implementa un controlador PID para regulación precisa de velocidad del motor:

**Algoritmo PID:**
```
error = setpoint - measured_value
integral = integral + error * dt
derivative = (error - previous_error) / dt
output = Kp * error + Ki * integral + Kd * derivative
```

**Protección Anti-Windup:**
- Limita el término integral cuando la salida satura
- Previene windup integral durante condiciones de error prolongadas
- Asegura control estable durante arranque y cambios de dirección

**Retroalimentación de Velocidad Basada en Encoder:**
- Encoder de cuadratura de 100 líneas proporciona 400 pulsos por revolución
- Lectura por interrupción asegura medición precisa de velocidad
- Velocidad calculada en cm/s basada en circunferencia de rueda
- Distancia acumulada para conteo de vueltas

**Frecuencia del Lazo de Control:**
- Cálculo PID a 50 Hz (cada 20ms)
- Transmisión de telemetría a 10 Hz (cada 100ms)
- Watchdog detiene motores si no se reciben comandos dentro de 500ms

### Procesamiento de Visión por Computadora

El sistema de visión usa OpenCV para detección de color en tiempo real y evasión de obstáculos:

**Segmentación en Espacio de Color HSV:**
- Convierte frames RGB de cámara a espacio de color HSV
- Define rangos de color para Rojo, Verde y Magenta (zona de estacionamiento)
- Rojo usa detección de doble rango (0-10° y 170-180° en hue)
- Verde: rango de hue 40-80°
- Magenta: rango de hue 140-170°

**Filtrado de Ruido:**
- Operación de apertura morfológica con kernel 5x5
- Elimina ruido pequeño y llena huecos pequeños
- Asegura detección robusta bajo condiciones de iluminación variables

**Análisis de Contornos:**
- Encuentra contornos en regiones enmascaradas de color
- Selecciona el contorno más grande por área
- Calcula centroide usando momentos de imagen
- Filtra detecciones por umbral de área mínimo (configurable)

**Procesamiento Asíncrono:**
- El procesamiento de visión corre en hilo de fondo
- El loop principal recibe la última detección sin bloquear
- Permite loop de control ~20 Hz mientras visión procesa a ~10 Hz
- Evita que retrasos de lectura de cámara afecten control de motor

**Dirección Proporcional:**
- Calcula ángulo de dirección basado en posición de centroide de obstáculo
- Obstáculos más cerca del centro del frame requieren giros más bruscos
- Fórmula: `angle = straight + factor * (evasion_angle - straight)`
- Factor varía de 0 (borde) a 1 (centro) para dirección suave

### Estacionamiento Basado en LiDAR

El sistema de estacionamiento usa el sensor LiDAR TF-Luna montado en un servo para detección de hueco y ejecución de maniobra:

**Escaneo con Servo:**
- El servo SG90 barre el LiDAR de 45° a 135°
- Tamaño de paso configurable (default 15°)
- Tiempo de sleep reducido a 80ms para optimización de rendimiento
- Retorna lista de tuplas (ángulo, distancia)

**Algoritmo de Detección de Hueco:**
- Busca 3 lecturas consecutivas por encima del umbral (80cm)
- Indica espacio abierto adecuado para estacionamiento
- Registra ángulo de hueco detectado para alineación

**Fases de Maniobra de Estacionamiento:**

1. **Fase de Escaneo:**
   - Detiene robot para escaneo estable
   - Barre LiDAR a través del rango de ángulos
   - Identifica ubicación del hueco de estacionamiento
   - Reintenta hasta 5 veces si no encuentra hueco

2. **Fase de Aproximación:**
   - Avanza lentamente por 1.5 segundos
   - Gira dirección para alinearse con hueco
   - Se detiene momentáneamente antes de reversa

3. **Fase de Reversa:**
   - Gira ruedas en ángulo para entrada en reversa
   - Reversa por 1.2 segundos
   - Endereza ruedas y continúa reversa
   - Gira en sentido opuesto para enderezar
   - Verifica distancia a pared con LiDAR
   - Ajusta posición si está muy cerca

4. **Fase de Enderezar:**
   - Avanza ligeramente para centrarse
   - Se detiene completamente
   - Marca estacionamiento como completado

**Manejo de Errores:**
- Todas las operaciones LiDAR envueltas en bloques try-except
- Retorna -1.0 en errores de lectura para degradación elegante
- Registra errores para propósitos de diagnóstico

### Protocolo de Comunicación Serial

La comunicación entre Raspberry Pi y Arduino usa un protocolo serial personalizado:

**Formato de Comando (Pi → Arduino):**
```
V:[velocity];A:[angle]\n
```
- Velocidad: 0-100 (porcentaje de velocidad máxima)
- Ángulo: 40-140 (ángulo de servo, 90 = recto)
- Ejemplo: `V:60;A:90\n` (60% velocidad, recto)

**Formato de Telemetría (Arduino → Pi):**
```
T:RPM:[rpm];CMS:[speed];DIST:[distance];A:[angle]\n
```
- RPM: Revoluciones por minuto del motor (0-5000)
- CMS: Velocidad en cm/s (0-200)
- DIST: Distancia acumulada en cm (0-100000)
- Ángulo: Ángulo actual de servo (40-140)
- Ejemplo: `T:RPM:1200;CMS:45;DIST:1234;A:90\n`

**Cola de Comandos Asíncrona:**
- Comandos colocados en cola (máximo 10 items)
- Hilo de trabajo dedicado procesa cola
- Envío no bloqueante desde loop principal
- Descarta comando más antiguo si cola llena (aceptable para control en tiempo real)
- Timeout de 50ms en cola get para prevenir bloqueo

**Validación de Telemetría:**
- Validación de rango en todos los valores recibidos
- Rechaza valores fuera de rangos esperados
- Previene que datos corruptos afecten control
- Registra fallos de validación para depuración

**Lógica de Reconexión:**
- Intento de reconexión automática en errores serial
- Hilo separado para reconexión para evitar bloqueo
- Backoff de 2 segundos entre intentos
- Degradación elegante si reconexión falla

## Descripción de Módulos

### Módulos de Firmware Arduino

**firmware_terreneitor.ino**
- Punto de entrada principal para firmware Arduino
- Inicializa comunicación serial a 115200 baud
- Configura interrupciones de encoder
- Inicializa driver de motor y servo
- Loop principal procesa comandos serial y corre control PID
- Envía telemetría cada 100ms
- Implementa timeout de watchdog (500ms) para seguridad

**config.h**
- Define asignaciones de pines para todo el hardware
- Declara variables globales compartidas entre módulos
- Define constantes físicas (circunferencia de rueda, etc.)
- Especifica parámetros PID (Kp, Ki, Kd)
- Define prototipos de función para todos los módulos

**motores.cpp**
- Controla driver de motor BTS7960 H-bridge
- Controla servo de dirección MG996R
- Implementa loop de control PID
- Aplica comandos de velocidad y ángulo
- Limita ángulos a rango seguro (40-140)
- Actualmente soporta solo movimiento hacia adelante

**sensores.cpp**
- Maneja rutinas de servicio de interrupción de encoder
- Cuenta ticks de encoder para cálculo de velocidad
- Calcula velocidad en cm/s basada en circunferencia de rueda
- Acumula distancia total recorrida
- Usa operaciones atómicas para lectura segura de interrupciones

**comunicacion.cpp**
- Inicializa comunicación serial
- Lee comandos entrantes línea por línea
- Parsea formato de comando: `V:[vel];A:[ang]\n`
- Actualiza setpoints de velocidad y ángulo
- Valida formato de comando
- Descarta comandos inválidos

**pid.cpp**
- Implementa estructura de controlador PID
- Proporciona función de inicialización
- Calcula salida PID desde error
- Implementa limitación anti-windup
- Proporciona función de reset para integral/derivada

**pid.h**
- Declara estructura PID con Kp, Ki, Kd, integral, derivada
- Declara prototipos de función
- Define constantes para anti-windup

### Módulos de Software Raspberry Pi

**main.py**
- Punto de entrada para software Raspberry Pi
- Carga configuración desde config.yaml
- Inicializa interfaces de hardware (Arduino, visión, LiDAR)
- Carga estrategia de navegación (para reglas sorpresa)
- Configura FSM con todos los estados
- Corre loop principal de FSM
- Maneja apagado elegante y limpieza de recursos

**config_loader.py**
- Lee y parsea archivo de configuración YAML
- Valida rangos de configuración (velocidades, ángulos)
- Proporciona métodos de acceso para secciones de configuración
- Retorna valores por defecto si configuración faltante
- Valida parámetros de competición

**comms_arduino.py**
- Maneja conexión serial con Arduino
- Implementa cola de comandos asíncrona
- Hilo de trabajo dedicado para envío de comandos
- Envío de comandos no bloqueante desde loop principal
- Lee y parsea telemetría con validación
- Implementa reconexión automática en errores
- Proporciona método de apagado seguro

**vision.py**
- Procesa frames de cámara para detección de color
- Implementa segmentación de color HSV
- Filtra ruido con operaciones morfológicas
- Calcula contornos y centroides
- Implementa procesamiento asíncrono con hilo de fondo
- Proporciona última detección sin bloquear
- Soporta detección de Rojo, Verde y Magenta

**lidar.py**
- Interfaz con sensor LiDAR TF-Luna
- Controla servo SG90 para escaneo
- Parsea tramas de datos de 9 bytes de TF-Luna
- Valida fuerza de señal para lecturas confiables
- Implementa escaneo de entorno con barrido de servo
- Tiempo de escaneo optimizado (80ms por paso)
- Proporciona lectura de distancia en centímetros

**fsm.py**
- Clase base para estados FSM
- Clase gestora FSM para transiciones de estado
- Maneja registro de estados
- Corre loop principal de FSM
- Gestiona ciclo de vida enter/execute/exit de estados
- Soporta salida elegante de FSM

**estado_inicio.py**
- Espera presionado de botón de inicio físico
- Usa gpiozero.Button para control GPIO
- Modo degradado con entrada por teclado si GPIO no disponible
- Inicializa todo el hardware al entrar
- Libera recursos de botón al salir

**estado_navegacion.py**
- Estado principal de navegación para ambos retos
- Implementa conteo de vueltas con encoder
- Cumple límite de tiempo de 3 minutos
- Detecta sección de meta para Reto Abierto
- Detecta violaciones de señales para Reto Obstáculos
- Retorna a sección de arranque después de 3 vueltas
- Usa procesamiento asíncrono de visión
- Implementa dirección proporcional para evasión de obstáculos
- Maneja lógica de ambos retos (Obstáculos y Abierto)

**estado_estacionar.py**
- Ejecuta estacionamiento automático en paralelo
- Algoritmo de estacionamiento multifase
- Usa LiDAR para detección de hueco
- Implementa fases de escaneo, aproximación, reversa y enderezar
- Manejo comprehensivo de errores para todas las operaciones de hardware
- Transiciona a FIN al completar

**estado_fin.py**
- Detiene todos los motores inmediatamente
- Centra servo de dirección
- Señala salida de FSM
- Asegura apagado seguro

**estrategia_base.py**
- Clase base abstracta para estrategias de navegación
- Define interfaz para implementación de estrategia
- Habilita inyección de estrategia para reglas sorpresa
- Requiere métodos decidir_accion() y get_nombre()

**estrategia_normal.py**
- Implementación concreta de estrategia de navegación normal
- Implementa lógica de evasión de obstáculos
- Rojo: evadir a izquierda (ángulo 130)
- Verde: evadir a derecha (ángulo 50)
- Magenta: línea recta (zona de estacionamiento)
- Dirección proporcional basada en posición de obstáculo

## Desafios de la competición

1. Fase Eléctrica y Chasis (Andrés y Sebastián): Ensamble de la estructura de baterías con el regulador XL4015 para asegurar la alimentación limpia e independiente de la Raspberry Pi y el Arduino. Cableado del puente H BTS7960 y fijación del motor principal.
2. Lazo de Control de Tracción (Ismael): Programación en el Arduino del control de velocidad del motor DC en lazo cerrado usando las interrupciones del encoder. El objetivo de este hito es lograr que el robot avance a una velocidad constante en centímetros por segundo sin importar el estado de carga de la batería.
3. Prototipado de Visión y Enlace (Ismael): Desarrollo del script vision.py en la Raspberry Pi utilizando imágenes estáticas de los bloques de color (rojo/verde) para definir los rangos HSV óptimos. En paralelo, establecer la comunicación serial básica para enviar tramas de texto sencillas del tipo V:50;A:90 (Velocidad: 50%, Ángulo: 90°) hacia el Arduino.
