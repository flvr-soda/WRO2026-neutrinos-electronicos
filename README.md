# Neutrinos Electrónicos WRO 2026

## Tabla de contenidos

- [Neutrinos Electrónicos WRO 2026](#neutrinos-electrónicos-wro-2026)
  - [Tabla de contenidos](#tabla-de-contenidos)
  - [Documentación](#documentación)
  - [Introducción](#introducción)
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
  - [Desafios de la competición](#desafios-de-la-competición)

## Documentación

## Introducción

| Nombre| Rol |
| :--- | :--- |
|Ismael Armada|Programador|
|Sebastián Vera|Mecánico|
|Andrés Lugo|Electricista|

## Descripción del proyecto

- Paradigma Seleccionado (Cerebro + Sistema Nervioso): Se descarta (POR AHORA) el uso de múltiples Arduinos para evitar problemas de latencia crítica en la transmisión de datos. Se mantiene un sistema híbrido centralizado: Raspberry Pi 4 como nodo maestro de alta velocidad y Arduino UNO como controlador dedicado de hardware en tiempo real.
- Aislamiento del Lazo de Control (PID): La lectura del encoder de cuadratura (100 líneas) y el control de potencia del motor DC (Puente H BTS7960) coexistirán en el mismo Arduino UNO. Esto garantiza un control de velocidad inmediato, fluido y sin retrasos de red.
- Flexibilidad ante "Reglas Sorpresa": Toda la lógica de la competición se desacopla del código fuente mediante un archivo de configuración centralizado (config.yaml). Modificaciones de última hora en los pits (sentido de giro, lado del estacionamiento, colores) se realizarán editando parámetros de texto plano, sin necesidad de reprogramar ni recompilar código.
- Modularidad de Software: En la Raspberry Pi se implementa una Máquina de Estados Finitos (FSM) basada en eventos, lo que facilita el desarrollo, testeo y depuración independiente de cada fase de la carrera (Inicio, Navegación, Esquiva, Estacionamiento).

## Hardware Usado (19/03/2026)

### Principal
- (SBC)  Raspberry Pi 4 Model B - 1GB
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
  │   └── modelos_3d/         		# Piezas STL y chasis del vehículo (para Sebastián)
  │
  ├── arduino/                		# Código fuente C++ (Arduino IDE)
  │   └── firmware_terreneitor/
  │   	├── firmware_terreneitor.ino    # Ciclo principal (Setup y Loop)
  │   	├── config.h                    # Asignación estática de Pines e Interrupciones
  │   	├── motores.cpp     	        # Control de puente H y servo MG996R
  │   	├── sensores.cpp                # Rutinas para Encoder, HC-SR04 y MPU6050
  │   	└── comunicacion.cpp	        # Parsers para el protocolo de mensajería Serial
  │
  └── raspberry_pi/                     # Código fuente Python (Procesamiento Principal)
    ├── requirements.txt                # Librerías necesarias (opencv-python, pyyaml, pyserial)
    ├── main.py                         # Script de arranque y orquestación del sistema
    ├── config.yaml                     # Parámetros de calibración y variables de competición
    └── src/                            # Módulos y librerías de control
    | ├── __init__.py
    | ├── config_loader.py		# Validador y lector del archivo YAML
    | ├── comms_arduino.py	        # Interfaz de comunicación Serial
    | ├── vision.py                     # Algoritmos de segmentación HSV (Cámara 120°)
    | └── lidar.py                      # Control del servo SG90 y lecturas del TF-Luna
    |
    └── estados/        	        # Clases independientes de la Máquina de Estados
      ├── __init__.py
      ├── fsm.py      		        # Controlador nativo de transiciones
      ├── estado_inicio.py              # Rutina de espera y lectura de condiciones iniciales
      ├── estado_navegacion.py 	        # Algoritmo de evasión de obstáculos (Rojo/Verde)
      ├── estado_estacionar.py          # Maniobra automática de parqueo en paralelo
      └── estado_fin.py                 # Detención segura del vehículo al cerrar la ronda
</pre>
## Desafios de la competición

1. Fase Eléctrica y Chasis (Andrés y Sebastián): Ensamble de la estructura de baterías con el regulador XL4015 para asegurar la alimentación limpia e independiente de la Raspberry Pi y el Arduino. Cableado del puente H BTS7960 y fijación del motor principal.
2. Lazo de Control de Tracción (Ismael): Programación en el Arduino del control de velocidad del motor DC en lazo cerrado usando las interrupciones del encoder. El objetivo de este hito es lograr que el robot avance a una velocidad constante en centímetros por segundo sin importar el estado de carga de la batería.
3. Prototipado de Visión y Enlace (Ismael): Desarrollo del script vision.py en la Raspberry Pi utilizando imágenes estáticas de los bloques de color (rojo/verde) para definir los rangos HSV óptimos. En paralelo, establecer la comunicación serial básica para enviar tramas de texto sencillas del tipo V:50;A:90 (Velocidad: 50%, Ángulo: 90°) hacia el Arduino.
