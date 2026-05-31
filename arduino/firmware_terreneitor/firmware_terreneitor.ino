#include "config.h"

// Definir la memoria real para las variables globales expuestas en config.h
int velocidadActual = 0;
int anguloActual = 90;
String inputString = "";
bool stringComplete = false;
unsigned long ultimoComandoMs = 0;

static unsigned long ultimoPIDMs = 0;
static unsigned long ultimoTelemetriaMs = 0;
const unsigned long TELEMETRIA_INTERVALO_MS = 100; // Enviar telemetría cada 100ms

void setup() {
  initComunicacion();
  initMotores();
  initSensores();
  
  unsigned long ahora = millis();
  ultimoPIDMs = ahora;
  ultimoTelemetriaMs = ahora;
  ultimoComandoMs = ahora;
}

void loop() {
  // Chequear recepción por serial continuamente sin bloquear
  chequearSerial();

  // Procesar comandos seriales si están disponibles
  if (stringComplete) {
    parsearComando(inputString);
    aplicarComandos();
    
    // Limpiar el string para la siguiente lectura
    inputString = "";
    stringComplete = false;
  }

  unsigned long ahora = millis();

  // Lazo PID a frecuencia fija (ej: cada 50ms)
  if (ahora - ultimoPIDMs >= PID_INTERVALO_MS) {
    float dt = (float)(ahora - ultimoPIDMs) / 1000.0f;
    ultimoPIDMs = ahora;
    
    actualizarVelocidad();
    aplicarPID(dt);
  }

  // Transmisión de telemetría a frecuencia fija (ej: cada 100ms)
  if (ahora - ultimoTelemetriaMs >= TELEMETRIA_INTERVALO_MS) {
    ultimoTelemetriaMs = ahora;
    enviarTelemetria();
  }

  // Watchdog de seguridad: Si no hay comandos en WATCHDOG_TIMEOUT_MS, detener motores
  if (ahora - ultimoComandoMs > WATCHDOG_TIMEOUT_MS) {
    if (velocidadActual != 0) {
      velocidadActual = 0;
      aplicarComandos();
    }
  }
}

void enviarTelemetria() {
  // Formato: T:RPM:x;CMS:y;A:z;
  float rpm = (velocidadActualCmS * 60.0f) / (3.14159265f * DIAMETRO_RUEDA_CM);
  Serial.print("T:RPM:");
  Serial.print((int)rpm);
  Serial.print(";CMS:");
  Serial.print((int)velocidadActualCmS);
  Serial.print(";A:");
  Serial.print(anguloActual);
  Serial.println(";");
}
