# Instalación del Servicio Systemd para Inicio Automático

Este documento describe cómo instalar los servicios systemd para el sistema principal y el sistema de emergencia.

## Servicios Disponibles

1. **wro-robot.service** - Sistema principal (raspberry_pi/main.py)
2. **wro-emergency.service** - Sistema de emergencia (EMERGENCIA/main.py)

**Nota:** Solo un servicio debe estar habilitado e iniciado a la vez.

## Requisitos Previos

1. El entorno virtual debe estar creado y con las dependencias instaladas:
   ```bash
   cd /home/pi/WRO2026-neutrinos-electronicos/raspberry_pi
   python3 -m venv env
   source env/bin/activate
   pip install -r requirements.txt
   ```

2. Los scripts deben tener permisos de ejecución:
   ```bash
   chmod +x /home/pi/WRO2026-neutrinos-electronicos/raspberry_pi/start_robot.sh
   chmod +x /home/pi/WRO2026-neutrinos-electronicos/EMERGENCIA/start_emergency.sh
   ```

## Instalación del Servicio

### Para el Sistema Principal (wro-robot.service)

1. **Copiar el archivo de servicio al directorio de systemd:**
   ```bash
   sudo cp /home/pi/WRO2026-neutrinos-electronicos/raspberry_pi/wro-robot.service /etc/systemd/system/
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

### Para el Sistema de Emergencia (wro-emergency.service)

1. **Copiar el archivo de servicio al directorio de systemd:**
   ```bash
   sudo cp /home/pi/WRO2026-neutrinos-electronicos/EMERGENCIA/wro-emergency.service /etc/systemd/system/
   ```

2. **Recargar la configuración de systemd:**
   ```bash
   sudo systemctl daemon-reload
   ```

3. **Habilitar el servicio para que se inicie al arranque:**
   ```bash
   sudo systemctl enable wro-emergency.service
   ```

4. **Iniciar el servicio manualmente (para probar):**
   ```bash
   sudo systemctl start wro-emergency.service
   ```

5. **Verificar el estado del servicio:**
   ```bash
   sudo systemctl status wro-emergency.service
   ```

### Cambiar entre Servicios

Para cambiar del sistema principal al de emergencia (o viceversa):

1. **Detener y deshabilitar el servicio actual:**
   ```bash
   sudo systemctl stop wro-robot.service
   sudo systemctl disable wro-robot.service
   ```

2. **Habilitar e iniciar el nuevo servicio:**
   ```bash
   sudo systemctl enable wro-emergency.service
   sudo systemctl start wro-emergency.service
   ```

## Gestión del Servicio

### Ver logs del servicio:
```bash
# Sistema principal
sudo journalctl -u wro-robot.service -f

# Sistema de emergencia
sudo journalctl -u wro-emergency.service -f
```

### Detener el servicio:
```bash
# Sistema principal
sudo systemctl stop wro-robot.service

# Sistema de emergencia
sudo systemctl stop wro-emergency.service
```

### Reiniciar el servicio:
```bash
# Sistema principal
sudo systemctl restart wro-robot.service

# Sistema de emergencia
sudo systemctl restart wro-emergency.service
```

### Deshabilitar el inicio automático:
```bash
# Sistema principal
sudo systemctl disable wro-robot.service

# Sistema de emergencia
sudo systemctl disable wro-emergency.service
```

## Solución de Problemas

### El servicio no inicia:
1. Verificar que el entorno virtual existe:
   ```bash
   ls -la /home/pi/WRO2026-neutrinos-electronicos/raspberry_pi/env/
   ```

2. Verificar que el script tiene permisos de ejecución:
   ```bash
   ls -la /home/pi/WRO2026-neutrinos-electronicos/raspberry_pi/start_robot.sh
   ```

3. Revisar los logs para errores:
   ```bash
   sudo journalctl -u wro-robot.service -n 50
   ```

### El servicio se reinicia constantemente:
- Esto puede indicar que el programa principal está fallando. Revisa los logs para ver el error específico.

## Notas Importantes

- El servicio se reiniciará automáticamente si el programa falla (configuración `Restart=always`)
- El servicio se reiniciará 10 segundos después de fallar (configuración `RestartSec=10`)
- Los logs se guardan en el journal de systemd y pueden verse con `journalctl`
- El servicio se ejecuta como usuario `pi` por seguridad
