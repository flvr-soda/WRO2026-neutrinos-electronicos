# SISTEMAS DE EMERGENCIA WRO (LiDAR DIRECTO)

Scripts de navegación reactiva y ultrarrápida sin dependencias de visión artificial o archivos YAML complejos.

---

## Modos Disponibles

### 1. `main.py` — Reto Abierto (Pista Libre)
Navegación reactiva con **LiDAR TF-Luna en posición fija frontal (90°)**.
- **Objetivo**: Completar 3 vueltas (12 esquinas) en el menor tiempo posible.
- **Lógica**: Avanza en línea recta a `VELOCIDAD_CRUCERO`. Al detectar la pared frontal (`<= 75 cm`), ejecuta viraje a la derecha (`50°`) a `VELOCIDAD_GIRO`, cuenta la esquina con filtro antirrebote y regresa a recta cuando el frente se despeja (`>= 110 cm`). Al llegar a 12 esquinas, frena por completo.

### 2. `main_obstaculos.py` — Reto con Obstáculos
Navegación con **LiDAR TF-Luna + Servo de paneo (GPIO 18)** para esquiva reactiva.
- **Objetivo**: Completar 3 vueltas esquivando pilares/obstáculos en los tramos rectos.
- **Lógica**:
  1. **Recta**: Avanza con LiDAR al frente (`90°`).
  2. **Detección de Obstáculo** (`<= 50 cm`): Hace un mini barrido rápido con el servo (`60°` izquierda, `120°` derecha) en ~200 ms.
  3. **Esquiva**: Gira hacia el lado con mayor distancia libre medida (`130°` izq o `50°` der) a `VELOCIDAD_ESQUIVA`.
  4. **Retorno**: Al despejarse el frente (`>= 90 cm`), reanuda la recta.
  5. **Esquinas de Pista** (`<= 75 cm`): Si detecta la pared perimetral, gira a la derecha y suma al contador de esquinas.

> **Nota sobre el color de pilares**: Al ser un algoritmo 100% basado en LiDAR sin cámara, esquiva por el lado con mayor espacio geométrico disponible.

---

## Requisitos Hardware

- **Raspberry Pi**:
  - LiDAR TF-Luna en `/dev/serial0` (115200 baud).
  - Servo de paneo LiDAR en `GPIO 18` (solo para `main_obstaculos.py`).
  - Botón de inicio físico en `GPIO 23` (Pin físico 16, Regla WRO 9.11).
  - Arduino conectado por USB (`/dev/ttyUSB*` o `/dev/ttyACM*`).
- **Arduino**:
  - Firmware `firmware_terreneitor`.

## Requisitos Software

```bash
pip install pyserial gpiozero
```

## Protocolo de Carrera (Regla WRO 9.11)

1. **Encendido**: El script/servicio inicia en modo `[STANDBY]`. El carro no se mueve.
2. **Listo**: Colocar el robot en la zona de salida.
3. **Inicio**: Presionar el botón físico en `GPIO 23` (o `ENTER` en consola si se ejecuta en terminal interactivo). Tras 0.5 segundos de estabilización, arranca automáticamente.
4. **Parada Automática**: Al completar las 12 esquinas (3 vueltas), se detiene y cierra comunicaciones de forma segura.

