#!/bin/bash
# Script de inicio para SISTEMA DE EMERGENCIA
# Navegación simple por paredes negras

cd "$(dirname "$0")"

echo "========================================"
echo "SISTEMA DE EMERGENCIA"
echo "Navegación simple por paredes negras"
echo "========================================"
echo ""

# Verificar que estamos en Raspberry Pi
if [ ! -f /proc/device-tree/model ]; then
    echo "ADVERTENCIA: No se detectó Raspberry Pi"
    echo "Este script está diseñado para ejecutarse en Raspberry Pi"
fi

# Verificar cámara
if ! command -v libcamera-hello &> /dev/null; then
    echo "ERROR: libcamera no está instalado"
    echo "Ejecuta: sudo apt install libcamera-tools"
    exit 1
fi

# Verificar dependencias de Python
echo "Verificando dependencias..."
python3 -c "import picamera2; import cv2; import numpy; import yaml" 2>/dev/null
if [ $? -ne 0 ]; then
    echo "ERROR: Faltan dependencias de Python"
    echo "Instala: pip install picamera2 opencv-python numpy pyyaml"
    exit 1
fi

echo "Iniciando navegación de emergencia..."
echo "Presiona Ctrl+C para detener"
echo ""

# Ejecutar programa principal
python3 main.py

echo ""
echo "Sistema de emergencia finalizado"
