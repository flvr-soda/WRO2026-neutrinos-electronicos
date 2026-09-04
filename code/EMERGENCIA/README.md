# SISTEMA DE EMERGENCIA

Navegación simple por paredes negras para completar el reto abierto (3 vueltas al circuito).

## Objetivo

Completar 3 vueltas al circuito de obstáculos sin chocar con las paredes delimitantes de color negro.

## Requisitos

- Raspberry Pi con cámara CSI
- Arduino conectado (puerto configurable en `config.yaml`)
- Dependencias de Python:
  ```bash
  pip install picamera2 opencv-python numpy pyyaml
  ```

## Uso

### Método 1: Script de inicio
```bash
cd EMERGENCIA
chmod +x start.sh
./start.sh
```

### Método 2: Ejecución directa
```bash
cd EMERGENCIA
python3 main.py
```

## Configuración

Editar `config.yaml` para ajustar parámetros:

- `navegacion.vueltas_objetivo`: Número de vueltas a completar (default: 3)
- `navegacion.velocidad_crucero`: Velocidad normal (default: 50)
- `vision.umbral_negro`: Sensibilidad de detección de negro (default: 50)

## Algoritmo

1. **Detección de paredes**: Analiza una línea horizontal del frame para detectar transiciones de negro a blanco
2. **Navegación**: 
   - Si detecta pared izquierda → gira derecha
   - Si detecta pared derecha → gira izquierda
   - Si detecta ambas paredes → esquina detectada, inicia giro
3. **Contador de vueltas**: Cada esquina detectada incrementa el contador
4. **Finalización**: Al completar 3 vueltas, detiene el robot

## Limitaciones

- Algoritmo simplificado, no optimizado para velocidad máxima
- Depende de iluminación constante para detección de negro
- No incluye detección de señales ni reglas avanzadas de WRO

## Cuándo usar

Este sistema es un respaldo de emergencia cuando el sistema principal en `raspberry_pi/` falle. No debe usarse como sistema principal en competición.
