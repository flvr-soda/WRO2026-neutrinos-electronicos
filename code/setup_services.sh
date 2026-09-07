#!/bin/bash
# Script de automatización para configuración de servicios systemd
# Automatiza la creación de entornos virtuales, instalación de dependencias,
# permisos de ejecución y gestión de servicios systemd

set -e  # Detener script si hay algún error

# Rutas del proyecto
PROJECT_DIR="/home/pi/WRO2026-neutrinos-electronicos"
RASPBERRY_PI_DIR="$PROJECT_DIR/code/raspberry_pi"
EMERGENCY_DIR="$PROJECT_DIR/code/EMERGENCIA"

# Archivos de servicio
ROBOT_SERVICE="$RASPBERRY_PI_DIR/wro-robot.service"
EMERGENCY_SERVICE="$EMERGENCY_DIR/wro-emergency.service"

# Scripts de inicio
ROBOT_SCRIPT="$RASPBERRY_PI_DIR/start_robot.sh"
EMERGENCY_SCRIPT="$EMERGENCY_DIR/start_emergency.sh"

# Requisitos
ROBOT_REQUIREMENTS="$RASPBERRY_PI_DIR/requirements.txt"
EMERGENCY_REQUIREMENTS="$EMERGENCY_DIR/requirements.txt"

# Nota: Ya no se usa config.yaml - el modo se detecta dinámicamente

# Colores para output
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
NC='\033[0m' # No Color

# Función para imprimir mensajes
print_info() {
    echo -e "${GREEN}[INFO]${NC} $1"
}

print_warn() {
    echo -e "${YELLOW}[WARN]${NC} $1"
}

print_error() {
    echo -e "${RED}[ERROR]${NC} $1"
}

# Verificar que estamos en el Raspberry Pi
check_raspberry_pi() {
    if [ ! -d "/home/pi" ]; then
        print_error "Este script debe ejecutarse en un Raspberry Pi"
        exit 1
    fi
}

# Crear entorno virtual e instalar dependencias
setup_virtualenv() {
    local target_dir=$1
    local requirements_file=$2
    local env_name=$3
    
    print_info "Configurando entorno virtual para $env_name..."
    
    # Verificar si ya existe el entorno virtual
    if [ -d "$target_dir/env" ]; then
        print_warn "El entorno virtual ya existe en $target_dir/env. Omitiendo creación."
    else
        print_info "Creando entorno virtual en $target_dir/env"
        cd "$target_dir"
        python3 -m venv env --system-site-packages
    fi
    
    # Activar entorno virtual e instalar dependencias
    print_info "Activando entorno virtual e instalando dependencias..."
    source "$target_dir/env/bin/activate"
    
    if [ -f "$requirements_file" ]; then
        pip install -r "$requirements_file"
        print_info "Dependencias instaladas correctamente para $env_name"
    else
        print_warn "No se encontró $requirements_file. Omitiendo instalación de dependencias para $env_name."
    fi
    
    deactivate
}

# Configurar ambos entornos virtuales
setup_all_virtualenvs() {
    print_info "=== Configurando entornos virtuales ==="
    
    # Configurar entorno para raspberry_pi
    setup_virtualenv "$RASPBERRY_PI_DIR" "$ROBOT_REQUIREMENTS" "sistema principal"
    
    # Configurar entorno para EMERGENCIA
    setup_virtualenv "$EMERGENCY_DIR" "$EMERGENCY_REQUIREMENTS" "sistema de emergencia"
    
    print_info "=== Entornos virtuales configurados ==="
}

# Dar permisos de ejecución a los scripts
setup_permissions() {
    print_info "Configurando permisos de ejecución..."
    
    if [ -f "$ROBOT_SCRIPT" ]; then
        chmod +x "$ROBOT_SCRIPT"
        print_info "Permisos dados a $ROBOT_SCRIPT"
    else
        print_warn "No se encontró $ROBOT_SCRIPT"
    fi
    
    if [ -f "$EMERGENCY_SCRIPT" ]; then
        chmod +x "$EMERGENCY_SCRIPT"
        print_info "Permisos dados a $EMERGENCY_SCRIPT"
    else
        print_warn "No se encontró $EMERGENCY_SCRIPT"
    fi
}

# Instalar servicio de systemd
install_service() {
    local service_name=$1
    local service_file=$2
    
    print_info "Instalando servicio $service_name..."
    
    # Verificar que el archivo de servicio existe
    if [ ! -f "$service_file" ]; then
        print_error "No se encontró $service_file"
        return 1
    fi
    
    # Copiar al directorio de systemd
    sudo cp "$service_file" "/etc/systemd/system/"
    
    # Recargar configuración de systemd
    sudo systemctl daemon-reload
    
    print_info "Servicio $service_name instalado correctamente"
}

# Habilitar e iniciar servicio
enable_service() {
    local service_name=$1
    
    print_info "Habilitando e iniciando servicio $service_name..."
    
    sudo systemctl enable "$service_name"
    sudo systemctl start "$service_name"
    
    print_info "Servicio $service_name habilitado e iniciado"
}

# Deshabilitar y detener servicio
disable_service() {
    local service_name=$1
    
    print_info "Deshabilitando y deteniendo servicio $service_name..."
    
    sudo systemctl stop "$service_name" 2>/dev/null || true
    sudo systemctl disable "$service_name" 2>/dev/null || true
    
    print_info "Servicio $service_name deshabilitado y detenido"
}

# Cambiar entre servicios
switch_service() {
    local target_service=$1
    
    if [ "$target_service" = "robot" ]; then
        print_info "Cambiando a servicio principal (wro-robot.service)..."
        disable_service "wro-emergency.service"
        install_service "wro-robot.service" "$ROBOT_SERVICE"
        enable_service "wro-robot.service"
    elif [ "$target_service" = "emergency" ]; then
        print_info "Cambiando a servicio de emergencia (wro-emergency.service)..."
        disable_service "wro-robot.service"
        install_service "wro-emergency.service" "$EMERGENCY_SERVICE"
        enable_service "wro-emergency.service"
    else
        print_error "Servicio no válido. Use 'robot' o 'emergency'"
        exit 1
    fi
}

# Verificar estado de servicio
check_status() {
    local service_name=$1
    
    print_info "Estado del servicio $service_name:"
    sudo systemctl status "$service_name"
}

# Mostrar logs de servicio
show_logs() {
    local service_name=$1
    
    print_info "Mostrando logs del servicio $service_name (Ctrl+C para salir):"
    sudo journalctl -u "$service_name" -f
}

# Instalación completa del servicio principal
install_robot_service() {
    print_info "=== Instalación completa del servicio principal ==="
    setup_all_virtualenvs
    setup_permissions
    install_service "wro-robot.service" "$ROBOT_SERVICE"
    enable_service "wro-robot.service"
    print_info "=== Servicio principal instalado correctamente ==="
}

# Instalación completa del servicio de emergencia
install_emergency_service() {
    print_info "=== Instalación completa del servicio de emergencia ==="
    print_info "Nota: El modo se detecta dinámicamente (abierto/obstáculos) por cámara"
    setup_all_virtualenvs
    setup_permissions
    install_service "wro-emergency.service" "$EMERGENCY_SERVICE"
    enable_service "wro-emergency.service"
    print_info "=== Servicio de emergencia instalado correctamente ==="
}

# Mostrar ayuda
show_help() {
    echo "Uso: $0 [comando] [opciones]"
    echo ""
    echo "Comandos:"
    echo "  setup              - Configurar entorno virtual, permisos y dependencias"
    echo "  install-robot      - Instalar y habilitar servicio principal (wro-robot.service)"
    echo "  install-emergency  - Instalar y habilitar servicio de emergencia (wro-emergency.service)"
    echo "  switch-robot       - Cambiar a servicio principal"
    echo "  switch-emergency   - Cambiar a servicio de emergencia"
    echo "  status [servicio]  - Ver estado del servicio (robot o emergency)"
    echo "  logs [servicio]    - Ver logs del servicio (robot o emergency)"
    echo "  help               - Mostrar esta ayuda"
    echo ""
    echo "Nota: El modo de emergencia se detecta dinámicamente por cámara"
    echo "      (abierto si no detecta colores, obstáculos si detecta colores)"
    echo ""
    echo "Ejemplos:"
    echo "  $0 setup"
    echo "  $0 install-robot"
    echo "  $0 switch-emergency"
    echo "  $0 status robot"
    echo "  $0 logs emergency"
}

# Función principal
main() {
    check_raspberry_pi
    
    case "${1:-help}" in
        setup)
            setup_all_virtualenvs
            setup_permissions
            ;;
        install-robot)
            install_robot_service
            ;;
        install-emergency)
            install_emergency_service
            ;;
        switch-robot)
            switch_service "robot"
            ;;
        switch-emergency)
            switch_service "emergency"
            ;;
        status)
            case "${2:-}" in
                robot)
                    check_status "wro-robot.service"
                    ;;
                emergency)
                    check_status "wro-emergency.service"
                    ;;
                *)
                    print_error "Especifique 'robot' o 'emergency'"
                    show_help
                    exit 1
                    ;;
            esac
            ;;
        logs)
            case "${2:-}" in
                robot)
                    show_logs "wro-robot.service"
                    ;;
                emergency)
                    show_logs "wro-emergency.service"
                    ;;
                *)
                    print_error "Especifique 'robot' o 'emergency'"
                    show_help
                    exit 1
                    ;;
            esac
            ;;
        help|--help|-h)
            show_help
            ;;
        *)
            print_error "Comando no reconocido"
            show_help
            exit 1
            ;;
    esac
}

# Ejecutar función principal
main "$@"
