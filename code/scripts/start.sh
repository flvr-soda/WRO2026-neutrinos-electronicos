#!/bin/bash
# Script parametrizado para iniciar el sistema robot
# Uso: ./start.sh [robot|safety]

# Verificar parámetro
if [ -z "$1" ]; then
    echo "Uso: $0 [robot|safety]"
    echo "  robot  - Sistema principal (main_sys)"
    echo "  safety - Sistema alternativo (safety_sys)"
    exit 1
fi

# Directorio del script
SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
cd "$SCRIPT_DIR/.."

# Activar entorno virtual compartido
if [ -d "env" ]; then
    source env/bin/activate
    echo "Entorno virtual compartido activado"
else
    echo "ERROR: No se encontró el directorio env/"
    echo "Ejecuta: python3 -m venv env"
    exit 1
fi

# Ejecutar programa según parámetro
case "$1" in
    robot)
        echo "Iniciando sistema principal..."
        cd main_sys
        python3 -m src.main
        ;;
    safety)
        echo "Iniciando sistema alternativo (modo dinámico)..."
        cd safety_sys
        python3 main_abierto.py
        ;;
    *)
        echo "ERROR: Parámetro no válido. Use 'robot' o 'safety'"
        exit 1
        ;;
esac

# Desactivar entorno virtual al salir
deactivate
