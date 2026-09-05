#!/bin/bash
# Script de inicio para SISTEMA DE EMERGENCIA
# Navegación reactiva con LiDAR

cd "$(dirname "$0")"

echo "========================================"
echo "SISTEMA DE EMERGENCIA (LiDAR DIRECTO)"
echo "3 Vueltas reactivas por detección frontal"
echo "========================================"
echo ""

# Verificar dependencias mínimas de Python
echo "Verificando dependencias..."
python3 -c "import serial; import gpiozero" 2>/dev/null
if [ $? -ne 0 ]; then
    echo "Instalando dependencias faltantes..."
    pip install pyserial gpiozero
fi


echo "Iniciando navegación de emergencia..."
echo "Presiona Ctrl+C para detener"
echo ""

# Ejecutar programa principal
python3 main.py

echo ""
echo "Sistema de emergencia finalizado."

