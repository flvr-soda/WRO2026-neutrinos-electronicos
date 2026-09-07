#!/bin/bash
# Script wrapper para activar venv y ejecutar el programa principal
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

# Ejecutar programa principal
echo "Iniciando programa principal..."
python3 src/main.py

# Desactivar entorno virtual al salir
deactivate
