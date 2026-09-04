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
  
  if (velocidadActual == 0) {
    analogWrite(PIN_RPWM, 0);
    analogWrite(PIN_LPWM, 0);
  } else {
    int velPct = constrain(velocidadActual, -100, 100);
    int pwmOut = map(abs(velPct), 0, 100, 0, 255);
    bool reversa = velPct < 0;
    
    // Control BTS7960: avance por RPWM, reversa por LPWM
    if (reversa) {
      analogWrite(PIN_RPWM, 0);
      analogWrite(PIN_LPWM, pwmOut);
    } else {
      analogWrite(PIN_RPWM, pwmOut);
      analogWrite(PIN_LPWM, 0);
    }
  }
}
