#ifndef PID_H
#define PID_H

struct PID {
    float kp;
    float ki;
    float kd;
    float integral;
    float ultimoError;
    float limiteMin;
    float limiteMax;
};

void pidInit(PID &pid, float kp, float ki, float kd, float limiteMin, float limiteMax);
float pidComputar(PID &pid, float target, float actual, float dt);
void pidReset(PID &pid);

#endif // PID_H
