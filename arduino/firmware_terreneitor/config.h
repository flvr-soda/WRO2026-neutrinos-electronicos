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
const int PIN_ENCODER_A = 2; // Pin de interrupción (Interrupt 0)
const int PIN_ENCODER_B = 3; // Pin de interrupción (Interrupt 1)

// Constantes físicas del robot
const float DIAMETRO_RUEDA_CM = 6.5;
const float TICKS_POR_VUELTA = 100.0;
const float MAX_VELOCIDAD_CMS = 120.0; // Velocidad en cm/s correspondiente a PWM = 255

// Constantes PID (pueden requerir ajuste en pista)
const float PID_KP = 2.0;
const float PID_KI = 0.5;
const float PID_KD = 0.1;
const unsigned long PID_INTERVALO_MS = 50; // Ejecutar lazo cada 50ms

// Variables globales (externas para compartir entre módulos)
extern int velocidadActual; // Consigna de velocidad recibida (0-255)
extern int anguloActual;
extern String inputString;
extern bool stringComplete;
extern unsigned long ultimoComandoMs;

extern volatile long encoderTicks;
extern float velocidadActualCmS;
extern float velocidadObjetivoCmS;
extern float distanciaTotalCm;

// Constantes de seguridad
const unsigned long WATCHDOG_TIMEOUT_MS = 500;

// Firmas de funciones (para enlazarse entre módulos C++ sin librerías extra)
void initMotores();
void aplicarComandos();
void aplicarPID(float dt);
void initComunicacion();
void chequearSerial();
void parsearComando(String comando);
void initSensores();
void actualizarVelocidad();
void enviarTelemetria();

#endif
