#ifndef CONFIG_H
#define CONFIG_H

#include <Arduino.h>

// Definición de pines
// Servo de Dirección
const int PIN_SERVO = 6;

// Puente H BTS7960
const int PIN_RPWM = 9; // PWM Derecha (Avanzar)
const int PIN_LPWM = 10; // PWM Izquierda (Retroceder)
const int PIN_R_EN = 7; // Enable Derecha
const int PIN_L_EN = 8; // Enable Izquierda 

// Constantes físicas del robot
// HC-SR04 Trasero
const int PIN_TRIG_TRASERO = 12;
const int PIN_ECHO_TRASERO = 13;

// Variables globales (externas para compartir entre módulos)
extern int velocidadActual; // Consigna de velocidad recibida (-100 a 100, porcentaje con signo; negativo = reversa)
extern int anguloActual;
extern String inputString;
extern bool stringComplete;
extern unsigned long ultimoComandoMs;

extern float mpu_z_acumulado;
extern float distancia_trasera_cm;

// Constantes de seguridad
const unsigned long WATCHDOG_TIMEOUT_MS = 500;

// Firmas de funciones (para enlazarse entre módulos C++ sin librerías extra)
void initMotores();
void aplicarComandos();
void initComunicacion();
void chequearSerial();
void parsearComando(String comando);
void initSensores();
void actualizarSensores();
void enviarTelemetria();

// Calibración y filtrado del giroscopio MPU6050
// Número de muestras para calibrar el bias del eje Z en setup() (robot debe estar QUIETO)
const int GYRO_BIAS_MUESTRAS = 300;
// Umbral de zona muerta: lecturas por debajo de este valor se descartan como ruido/vibración
// 1.5 °/s cubre la mayoría del ruido del BTS7960 en banco de pruebas; subir si hay desfase en movimiento
const float GYRO_DEADBAND_DPS = 1.5f;

#endif
