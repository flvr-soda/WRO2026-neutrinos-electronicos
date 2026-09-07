#!/bin/bash
# Script de automatización para configuración de servicios systemd
# Automatiza la creación de entornos virtuales, instalación de dependencias,
# permisos de ejecución y gestión de servicios systemd

set -e  # Detener script si hay algún error

# Rutas del proyecto
PROJECT_DIR="/home/pi/WRO2026-neutrinos-electronicos"
CODE_DIR="$PROJECT_DIR/code"
SCRIPTS_DIR="$CODE_DIR/scripts"
SERVICES_DIR="$CODE_DIR/services"

# Archivos de servicio
ROBOT_SERVICE="$SERVICES_DIR/wro-robot.service"
SAFETY_SERVICE="$SERVICES_DIR/wro-safety.service"

# Script parametrizado
START_SCRIPT="$SCRIPTS_DIR/start.sh"

# Requisitos compartidos
REQUIREMENTS="$CODE_DIR/requirements.txt"

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

# Crear entorno virtual compartido e instalar dependencias
setup_virtualenv() {
    local target_dir=$1
    local requirements_file=$2
    local env_name=$3
    
    print_info "Configurando entorno virtual compartido para $env_name..."
    
    # Verificar si ya existe el entorno virtual
    if [ -d "$target_dir/env" ]; then
        print_warn "El entorno virtual ya existe en $target_dir/env. Omitiendo creación."
    else
        print_info "Creando entorno virtual compartido en $target_dir/env"
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

# Configurar entorno virtual compartido
setup_all_virtualenvs() {
    print_info "=== Configurando entorno virtual compartido ==="
    
    # Configurar entorno compartido en code/
    setup_virtualenv "$CODE_DIR" "$REQUIREMENTS" "sistemas principal y alternativo"
    
    print_info "=== Entorno virtual compartido configurado ==="
}

# Dar permisos de ejecución a los scripts
setup_permissions() {
    print_info "Configurando permisos de ejecución..."
    
    if [ -f "$START_SCRIPT" ]; then
        chmod +x "$START_SCRIPT"
        print_info "Permisos dados a $START_SCRIPT"
    else
        print_warn "No se encontró $START_SCRIPT"
    fi
    
    if [ -f "$SCRIPTS_DIR/setup_services.sh" ]; then
        chmod +x "$SCRIPTS_DIR/setup_services.sh"
        print_info "Permisos dados a setup_services.sh"
    else
        print_warn "No se encontró setup_services.sh"
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
        disable_service "wro-safety.service"
        install_service "wro-robot.service" "$ROBOT_SERVICE"
        enable_service "wro-robot.service"
    elif [ "$target_service" = "safety" ]; then
        print_info "Cambiando a servicio alternativo (wro-safety.service)..."
        disable_service "wro-robot.service"
        install_service "wro-safety.service" "$SAFETY_SERVICE"
        enable_service "wro-safety.service"
    else
        print_error "Servicio no válido. Use 'robot' o 'safety'"
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

# Instalación completa del servicio alternativo
install_safety_service() {
    print_info "=== Instalación completa del servicio alternativo ==="
    print_info "Nota: El modo se detecta dinámicamente (abierto/obstáculos) por cámara"
    setup_all_virtualenvs
    setup_permissions
    install_service "wro-safety.service" "$SAFETY_SERVICE"
    enable_service "wro-safety.service"
    print_info "=== Servicio alternativo instalado correctamente ==="
}

# Mostrar ayuda
show_help() {
    echo "Uso: $0 [comando] [opciones]"
    echo ""
    echo "Comandos:"
    echo "  setup              - Configurar entorno virtual, permisos y dependencias"
    echo "  install-robot      - Instalar y habilitar servicio principal (wro-robot.service)"
    echo "  install-safety     - Instalar y habilitar servicio alternativo (wro-safety.service)"
    echo "  switch-robot       - Cambiar a servicio principal"
    echo "  switch-safety      - Cambiar a servicio alternativo"
    echo "  status [servicio]  - Ver estado del servicio (robot o safety)"
    echo "  logs [servicio]    - Ver logs del servicio (robot o safety)"
    echo "  help               - Mostrar esta ayuda"
    echo ""
    echo "Nota: El modo alternativo se detecta dinámicamente por cámara"
    echo "      (abierto si no detecta colores, obstáculos si detecta colores)"
    echo ""
    echo "Ejemplos:"
    echo "  $0 setup"
    echo "  $0 install-robot"
    echo "  $0 switch-safety"
    echo "  $0 status robot"
    echo "  $0 logs safety"
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
        install-safety)
            install_safety_service
            ;;
        switch-robot)
            switch_service "robot"
            ;;
        switch-safety)
            switch_service "safety"
            ;;
        status)
            case "${2:-}" in
                robot)
                    check_status "wro-robot.service"
                    ;;
                safety)
                    check_status "wro-safety.service"
                    ;;
                *)
                    print_error "Especifique 'robot' o 'safety'"
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
                safety)
                    show_logs "wro-safety.service"
                    ;;
                *)
                    print_error "Especifique 'robot' o 'safety'"
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
