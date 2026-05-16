#include "config.h"

// Definir la memoria real para las variables globales expuestas en config.h
int velocidadActual = 0;
int anguloActual = 90;
String inputString = "";
bool stringComplete = false;

void setup() {
  initComunicacion();
  initMotores();
  initSensores();
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
}
