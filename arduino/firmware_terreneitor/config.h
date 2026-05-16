#ifndef CONFIG_H
#define CONFIG_H

#include <Arduino.h>

// Definición de pines
// Servo de Dirección
const int PIN_SERVO = 9;

// Puente H BTS7960
const int PIN_RPWM = 5; // PWM Derecha (Avanzar)
const int PIN_LPWM = 6; // PWM Izquierda (Retroceder)
const int PIN_R_EN = 7; // Enable Derecha
const int PIN_L_EN = 8; // Enable Izquierda

// Pines futuros
const int PIN_ENCODER_A = 2; // Pin de interrupción
const int PIN_ENCODER_B = 3;

// Variables globales (externas para compartir entre módulos)
extern int velocidadActual;
extern int anguloActual;
extern String inputString;
extern bool stringComplete;

// Firmas de funciones (para enlazarse entre módulos C++ sin librerías extra)
void initMotores();
void aplicarComandos();
void initComunicacion();
void chequearSerial();
void parsearComando(String comando);
void initSensores();

#endif
