#!/bin/bash
# Script wrapper para activar venv y ejecutar el programa alternativo
# Este script es usado por el servicio systemd

# Directorio del script
SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
cd "$SCRIPT_DIR"

# Activar entorno virtual compartido en code/
if [ -d "../env" ]; then
    source ../env/bin/activate
    echo "Entorno virtual compartido activado"
else
    echo "ERROR: No se encontró el directorio ../env/"
    echo "Ejecuta: cd .. && python3 -m venv env"
    exit 1
fi

# Ejecutar programa alternativo (modo dinámico)
echo "Iniciando sistema alternativo (modo dinámico)..."
python3 main.py

# Desactivar entorno virtual al salir
deactivate
