#!/bin/bash
# Script wrapper para activar venv y ejecutar el programa de emergencia
# Este script es usado por el servicio systemd

# Directorio del script
SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
cd "$SCRIPT_DIR"

# Activar entorno virtual del directorio principal
if [ -d "env" ]; then
    source env/bin/activate
    echo "Entorno virtual activado"
else
    echo "ERROR: No se encontró el directorio env/"
    echo "Ejecuta: python3 -m venv env"
    exit 1
fi

# Leer configuración para determinar qué main ejecutar
MODO=$(python3 -c "import yaml; config = yaml.safe_load(open('config.yaml')); print(config.get('modo', 'abierto'))" 2>/dev/null || echo "abierto")

echo "Modo de emergencia: $MODO"

# Ejecutar programa de emergencia según el modo
if [ "$MODO" = "obstaculos" ]; then
    echo "Iniciando sistema de emergencia (reto de obstáculos)..."
    python3 main_obstaculos.py
else
    echo "Iniciando sistema de emergencia (reto abierto)..."
    python3 main.py
fi

# Desactivar entorno virtual al salir
deactivate
