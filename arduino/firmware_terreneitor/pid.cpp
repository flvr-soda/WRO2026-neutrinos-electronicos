#include "pid.h"

void pidInit(PID &pid, float kp, float ki, float kd, float limiteMin, float limiteMax) {
    pid.kp = kp;
    pid.ki = ki;
    pid.kd = kd;
    pid.integral = 0.0f;
    pid.ultimoError = 0.0f;
    pid.limiteMin = limiteMin;
    pid.limiteMax = limiteMax;
}

float pidComputar(PID &pid, float target, float actual, float dt) {
    if (dt <= 0.0f) return 0.0f;
    
    float error = target - actual;
    
    // Proporcional
    float pOut = pid.kp * error;
    
    // Integral
    pid.integral += error * dt;
    float iOut = pid.ki * pid.integral;
    
    // Derivativo
    float derivativo = (error - pid.ultimoError) / dt;
    float dOut = pid.kd * derivativo;
    
    pid.ultimoError = error;
    
    float output = pOut + iOut + dOut;
    
    // Anti-windup usando clamping
    if (output > pid.limiteMax) {
        if (error > 0.0f) {
            pid.integral -= error * dt; // deshacer la acumulación si satura en la misma dirección
        }
        output = pid.limiteMax;
    } else if (output < pid.limiteMin) {
        if (error < 0.0f) {
            pid.integral -= error * dt;
        }
        output = pid.limiteMin;
    }
    
    return output;
}

void pidReset(PID &pid) {
    pid.integral = 0.0f;
    pid.ultimoError = 0.0f;
}
