#include "config.h"

// Definiciones de variables globales para sensores
volatile long encoderTicks = 0;
float velocidadActualCmS = 0.0;
float velocidadObjetivoCmS = 0.0;
static unsigned long ultimaMedicionUs = 0;

// Interrupt Service Routine (ISR) para el Encoder
void encoderISR() {
  // Cuadratura simple: leer canales A y B
  if (digitalRead(PIN_ENCODER_A) == digitalRead(PIN_ENCODER_B)) {
    encoderTicks++;
  } else {
    encoderTicks--;
  }
}

void initSensores() {
  pinMode(PIN_ENCODER_A, INPUT_PULLUP);
  pinMode(PIN_ENCODER_B, INPUT_PULLUP);
  
  // Asociar la interrupción al Pin A (en el UNO, D2 es interrupt 0)
  attachInterrupt(digitalPinToInterrupt(PIN_ENCODER_A), encoderISR, CHANGE);
  
  ultimaMedicionUs = micros();
}

void actualizarVelocidad() {
  unsigned long ahoraUs = micros();
  unsigned long deltaUs = ahoraUs - ultimaMedicionUs;
  if (deltaUs == 0) return;
  
  // Leer y limpiar ticks de forma atómica
  noInterrupts();
  long ticks = encoderTicks;
  encoderTicks = 0;
  interrupts();
  
  ultimaMedicionUs = ahoraUs;
  
  // Convertir ticks a centímetros por segundo:
  // velocidad = (ticks / TICKS_POR_VUELTA) * (PI * DIAMETRO_RUEDA_CM) / (deltaUs / 1,000,000)
  float revoluciones = (float)ticks / TICKS_POR_VUELTA;
  float distanciaCm = revoluciones * (3.14159265f * DIAMETRO_RUEDA_CM);
  float deltaSegundos = (float)deltaUs / 1000000.0f;
  
  velocidadActualCmS = distanciaCm / deltaSegundos;
}

