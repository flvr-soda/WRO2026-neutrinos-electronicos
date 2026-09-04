#include "config.h"

// Definir la memoria real para las variables globales expuestas en config.h
int velocidadActual = 0;
int anguloActual = 90;
String inputString = "";
bool stringComplete = false;
unsigned long ultimoComandoMs = 0;

static unsigned long ultimoSensoresMs = 0;
static unsigned long ultimoTelemetriaMs = 0;
const unsigned long SENSORES_INTERVALO_MS = 10; // Leer sensores cada 10ms
const unsigned long TELEMETRIA_INTERVALO_MS = 100; // Enviar telemetría cada 100ms

void setup() {
  initComunicacion();
  initMotores();
  initSensores();
  
  unsigned long ahora = millis();
  ultimoSensoresMs = ahora;
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

  // Lazo de sensores a frecuencia fija
  if (ahora - ultimoSensoresMs >= SENSORES_INTERVALO_MS) {
    ultimoSensoresMs = ahora;
    actualizarSensores();
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
  // Formato: T:Z:x;A:y;
  Serial.print("T:Z:");
  Serial.print(mpu_z_acumulado, 1);
  Serial.print(";A:");
  Serial.print(anguloActual);
  Serial.print(";U:");
  Serial.print(distancia_trasera_cm);
  Serial.println(";");
}
