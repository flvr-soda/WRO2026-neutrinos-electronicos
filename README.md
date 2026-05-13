# Neutrinos Electrónicos WRO 2026

## Tabla de contenidos

- [Documentación](#documentación)
- [Introducción al equipo](#introducción-al-equipo)
- [Descripción del proyecto](#descripcion-del-proyecto)
- [Hardware Usado](#hardware-usado)
- [Software y librerias](#software-y-librerias)
- [Desafios de la competición](#desafios-de-la-competición)

## Documentación

## Neutrinos Electrónicos

| Nombre| Rol |
| :--- | :--- |
|Ismael Armada|Programador|
|Sebastián Vera|Mecánico|
|Andrés Lugo|Electricista|

## Descripción del proyecto

- Documentación y codebase del Terreneitor, un vehículo autonomo para la competición en la World Robot Olympiad 2026.

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

## Desafios de la competición

1. Implementar visión por computador para la identificación y sorteo de obstaculos. 
2. Lazo de control de tracción para avance del robot a una velocidad constante sin importar nivel de carga de la bateria.
3. Ensamble de estructuras de baterias y fijación del motor principal.
