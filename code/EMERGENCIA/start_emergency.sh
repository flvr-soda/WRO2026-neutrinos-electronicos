#!/bin/bash
# Script wrapper para activar venv y ejecutar el programa de emergencia
# Este script es usado por el servicio systemd

# Directorio del script
SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
cd "$SCRIPT_DIR"

# Activar entorno virtual del directorio principal
if [ -d "../env" ]; then
    source ../env/bin/activate
    echo "Entorno virtual activado"
else
    echo "ERROR: No se encontró el directorio env/ en el directorio principal"
    echo "Ejecuta: cd .. && python3 -m venv env"
    exit 1
fi

# Ejecutar programa de emergencia
echo "Iniciando sistema de emergencia..."
python3 main.py

# Desactivar entorno virtual al salir
deactivate
