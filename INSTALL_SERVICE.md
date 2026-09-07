# Instalación del Servicio Systemd para Inicio Automático

Este documento describe cómo instalar los servicios systemd para el sistema principal y el sistema alternativo.

## Servicios Disponibles

1. **wro-robot.service** - Sistema principal (main_sys/src/main.py)
2. **wro-safety.service** - Sistema alternativo (safety_sys/main.py)

**Nota:** Solo un servicio debe estar habilitado e iniciado a la vez.

## Instalación Automatizada (Recomendado)

El script `setup_services.sh` automatiza todo el proceso de instalación:

```bash
cd /home/pi/WRO2026-neutrinos-electronicos/code

# Configurar entorno virtual compartido y permisos
./setup_services.sh setup

# Instalar y habilitar sistema principal
./setup_services.sh install-robot

# Cambiar a sistema alternativo
./setup_services.sh switch-safety

# Verificar estado
./setup_services.sh status robot
./setup_services.sh status safety

# Ver logs
./setup_services.sh logs robot
./setup_services.sh logs safety
```

## Instalación Manual

### Requisitos Previos

1. **Crear entorno virtual compartido:**
   ```bash
   cd /home/pi/WRO2026-neutrinos-electronicos/code
   python3 -m venv env
   source env/bin/activate
   pip install -r requirements.txt
   deactivate
   ```

2. **Dar permisos de ejecución a los scripts:**
   ```bash
   chmod +x /home/pi/WRO2026-neutrinos-electronicos/code/main_sys/start_robot.sh
   chmod +x /home/pi/WRO2026-neutrinos-electronicos/code/safety_sys/start_safety.sh
   chmod +x /home/pi/WRO2026-neutrinos-electronicos/code/setup_services.sh
   ```

### Para el Sistema Principal (wro-robot.service)

1. **Copiar el archivo de servicio al directorio de systemd:**
   ```bash
   sudo cp /home/pi/WRO2026-neutrinos-electronicos/code/main_sys/wro-robot.service /etc/systemd/system/
   ```

2. **Recargar la configuración de systemd:**
   ```bash
   sudo systemctl daemon-reload
   ```

3. **Habilitar el servicio para que se inicie al arranque:**
   ```bash
   sudo systemctl enable wro-robot.service
   ```

4. **Iniciar el servicio manualmente (para probar):**
   ```bash
   sudo systemctl start wro-robot.service
   ```

5. **Verificar el estado del servicio:**
   ```bash
   sudo systemctl status wro-robot.service
   ```

### Para el Sistema Alternativo (wro-safety.service)

1. **Copiar el archivo de servicio al directorio de systemd:**
   ```bash
   sudo cp /home/pi/WRO2026-neutrinos-electronicos/code/safety_sys/wro-safety.service /etc/systemd/system/
   ```

2. **Recargar la configuración de systemd:**
   ```bash
   sudo systemctl daemon-reload
   ```

3. **Habilitar el servicio para que se inicie al arranque:**
   ```bash
   sudo systemctl enable wro-safety.service
   ```

4. **Iniciar el servicio manualmente (para probar):**
   ```bash
   sudo systemctl start wro-safety.service
   ```

5. **Verificar el estado del servicio:**
   ```bash
   sudo systemctl status wro-safety.service
   ```

### Cambiar entre Servicios

Para cambiar del sistema principal al alternativo (o viceversa):

1. **Detener y deshabilitar el servicio actual:**
   ```bash
   sudo systemctl stop wro-robot.service
   sudo systemctl disable wro-robot.service
   ```

2. **Habilitar e iniciar el nuevo servicio:**
   ```bash
   sudo systemctl enable wro-safety.service
   sudo systemctl start wro-safety.service
   ```

## Gestión del Servicio

### Ver logs del servicio:
```bash
# Sistema principal
sudo journalctl -u wro-robot.service -f

# Sistema alternativo
sudo journalctl -u wro-safety.service -f
```

### Detener el servicio:
```bash
# Sistema principal
sudo systemctl stop wro-robot.service

# Sistema alternativo
sudo systemctl stop wro-safety.service
```

### Reiniciar el servicio:
```bash
# Sistema principal
sudo systemctl restart wro-robot.service

# Sistema alternativo
sudo systemctl restart wro-safety.service
```

### Deshabilitar el inicio automático:
```bash
# Sistema principal
sudo systemctl disable wro-robot.service

# Sistema alternativo
sudo systemctl disable wro-safety.service
```

## Solución de Problemas

### El servicio no inicia:
1. Verificar que el entorno virtual compartido existe:
   ```bash
   ls -la /home/pi/WRO2026-neutrinos-electronicos/code/env/
   ```

2. Verificar que los scripts tienen permisos de ejecución:
   ```bash
   ls -la /home/pi/WRO2026-neutrinos-electronicos/code/main_sys/start_robot.sh
   ls -la /home/pi/WRO2026-neutrinos-electronicos/code/safety_sys/start_safety.sh
   ```

3. Revisar los logs para errores:
   ```bash
   sudo journalctl -u wro-robot.service -n 50
   sudo journalctl -u wro-safety.service -n 50
   ```

### El servicio se reinicia constantemente:
- Esto puede indicar que el programa principal está fallando. Revisa los logs para ver el error específico.

## Notas Importantes

- **Entorno virtual compartido:** Ambos sistemas usan el mismo entorno virtual en `code/env/` para optimizar espacio y mantener consistencia.
- **Configuración directa:** El sistema principal usa `config.py` en lugar de archivos YAML para simplicidad.
- **Restart automático:** El servicio se reiniciará automáticamente si el programa falla (configuración `Restart=always`)
- **Delay de reinicio:** El servicio se reiniciará 10 segundos después de fallar (configuración `RestartSec=10`)
- **Logs:** Los logs se guardan en el journal de systemd y pueden verse con `journalctl`
- **Usuario:** El servicio se ejecuta como usuario `pi` por seguridad
