#include "config.h"
#include <Servo.h>

Servo servoDireccion;

void initMotores() {
  // Configurar Servo
  servoDireccion.attach(PIN_SERVO);
  servoDireccion.write(anguloActual); // Posición central por defecto
  
  // Configurar pines del BTS7960
  pinMode(PIN_RPWM, OUTPUT);
  pinMode(PIN_LPWM, OUTPUT);
  pinMode(PIN_R_EN, OUTPUT);
  pinMode(PIN_L_EN, OUTPUT);
  
  // Activar los Enable del puente H
  digitalWrite(PIN_R_EN, HIGH);
  digitalWrite(PIN_L_EN, HIGH);
  
  // Asegurar que los motores estén detenidos
  analogWrite(PIN_RPWM, 0);
  analogWrite(PIN_LPWM, 0);
}

void aplicarComandos() {
  // Limitar ángulo de seguridad (ej. 40 a 140 grados)
  int anguloSeguro = constrain(anguloActual, 40, 140);
  servoDireccion.write(anguloSeguro);
  
  // Limitar velocidad de 0 a 255 (solo hacia adelante para este MVP)
  int pwmSpeed = constrain(velocidadActual, 0, 255);
  
  // Control BTS7960
  if (pwmSpeed > 0) {
    analogWrite(PIN_RPWM, pwmSpeed);
    analogWrite(PIN_LPWM, 0); // Asegurar que no retrocede
  } else {
    // Detener motores
    analogWrite(PIN_RPWM, 0);
    analogWrite(PIN_LPWM, 0);
  }
}
