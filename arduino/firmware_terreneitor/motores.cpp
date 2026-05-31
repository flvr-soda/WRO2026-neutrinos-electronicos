#include "config.h"
#include "pid.h"
#include <Servo.h>

Servo servoDireccion;
PID motorPID;

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
  
  // Inicializar PID de velocidad: Kp, Ki, Kd, minOutput, maxOutput
  pidInit(motorPID, PID_KP, PID_KI, PID_KD, 0.0f, 255.0f);
}

void aplicarComandos() {
  // Limitar ángulo de seguridad (ej. 40 a 140 grados)
  int anguloSeguro = constrain(anguloActual, 40, 140);
  servoDireccion.write(anguloSeguro);
  
  // Si la velocidad consignada es cero, forzar parada y reiniciar PID
  if (velocidadActual == 0) {
    velocidadObjetivoCmS = 0.0f;
    analogWrite(PIN_RPWM, 0);
    analogWrite(PIN_LPWM, 0);
    pidReset(motorPID);
  } else {
    // Calcular velocidad objetivo en cm/s basada en la entrada cruda PWM (0-255)
    velocidadObjetivoCmS = ((float)velocidadActual / 255.0f) * MAX_VELOCIDAD_CMS;
  }
}

void aplicarPID(float dt) {
  // Si no hay consigna de movimiento, asegurar parada
  if (velocidadObjetivoCmS <= 0.01f) {
    analogWrite(PIN_RPWM, 0);
    analogWrite(PIN_LPWM, 0);
    return;
  }
  
  // Calcular salida del PID (esperando valores de velocidad en cm/s positivos)
  float u = pidComputar(motorPID, velocidadObjetivoCmS, velocidadActualCmS, dt);
  int pwmOut = (int)u;
  pwmOut = constrain(pwmOut, 0, 255);
  
  // Control BTS7960 (solo avance por ahora)
  analogWrite(PIN_RPWM, pwmOut);
  analogWrite(PIN_LPWM, 0);
}

