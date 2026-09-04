#include "config.h"
#include <Wire.h>

float mpu_z_acumulado = 0.0;
float distancia_trasera_cm = -1.0;
static unsigned long ultimaMedicionUs = 0;
const int MPU_ADDR = 0x68;

// Bias del eje Z medido durante la calibración en setup() (se resta en cada lectura)
static float gyro_z_bias = 0.0f;

// Contador para alternar la lectura del HC-SR04 (M-1: evita bloquear el loop con pulseIn cada 10ms)
static unsigned int ciclo_sensor = 0;

// Filtrado de media móvil para ultrasonido (reduce ruido)
static float historico_distancias[5] = {-1.0, -1.0, -1.0, -1.0, -1.0};
static int idx_historico = 0;
const float DISTANCIA_EMERGENCIA_CM = 5.0;  // Distancia crítica para detener motores

// Declaración externa para poder detener motores en emergencia
extern void aplicarComandos();
extern int velocidadActual;

void initSensores() {
  pinMode(PIN_TRIG_TRASERO, OUTPUT);
  pinMode(PIN_ECHO_TRASERO, INPUT);
  digitalWrite(PIN_TRIG_TRASERO, LOW);

  Wire.begin();
  Wire.beginTransmission(MPU_ADDR);
  Wire.write(0x6B);  // PWR_MGMT_1 register
  Wire.write(0);     // set to zero (wakes up the MPU-6050)
  Wire.endTransmission(true);

  // ── Calibración de bias del eje Z ─────────────────────────────────────
  // El robot debe estar COMPLETAMENTE QUIETO durante esta fase.
  // Se promedian GYRO_BIAS_MUESTRAS lecturas para estimar el offset estático.
  // Esta rutina dura aprox. GYRO_BIAS_MUESTRAS * 5ms = 1.5s con 300 muestras.
  long suma_z = 0;
  for (int i = 0; i < GYRO_BIAS_MUESTRAS; i++) {
    Wire.beginTransmission(MPU_ADDR);
    Wire.write(0x47); // GYRO_ZOUT_H
    Wire.endTransmission(false);
    Wire.requestFrom(MPU_ADDR, 2, true);
    if (Wire.available() == 2) {
      int16_t raw = Wire.read() << 8 | Wire.read();
      suma_z += raw;
    }
    delay(5);
  }
  gyro_z_bias = (float)suma_z / (float)GYRO_BIAS_MUESTRAS / 131.0f;
  // ──────────────────────────────────────────────────────────────────────

  ultimaMedicionUs = micros();
}

void actualizarSensores() {
  unsigned long ahoraUs = micros();
  unsigned long deltaUs = ahoraUs - ultimaMedicionUs;
  if (deltaUs == 0) return;

  Wire.beginTransmission(MPU_ADDR);
  Wire.write(0x47); // GYRO_ZOUT_H
  Wire.endTransmission(false);
  Wire.requestFrom(MPU_ADDR, 2, true); // read 2 bytes

  if (Wire.available() == 2) {
    int16_t gyroZ = Wire.read() << 8 | Wire.read();

    // Convertir a °/s y restar bias calibrado en arranque
    float gyroZ_deg_s = ((float)gyroZ / 131.0f) - gyro_z_bias;

    // Zona muerta configurable: filtra vibración residual del motor en movimiento
    if (abs(gyroZ_deg_s) < GYRO_DEADBAND_DPS) {
      gyroZ_deg_s = 0.0f;
    }

    // Integrar para obtener grados acumulados
    float deltaSegundos = (float)deltaUs / 1000000.0f;
    mpu_z_acumulado += gyroZ_deg_s * deltaSegundos;
  }

  // M-2: actualizar timestamp justo después de la lectura I2C (no al final del ciclo)
  // para que deltaUs refleje exactamente el intervalo entre lecturas del giroscopio
  ultimaMedicionUs = ahoraUs;

  // M-1: Lectura HC-SR04 cada 5 ciclos (~50ms) para no bloquear el loop con pulseIn
  // pulseIn(timeout=6000us) consume hasta 6ms — en cada ciclo de 10ms eso era el 60% del tiempo
  ciclo_sensor++;
  if (ciclo_sensor >= 5) {
    ciclo_sensor = 0;
    digitalWrite(PIN_TRIG_TRASERO, HIGH);
    delayMicroseconds(10);
    digitalWrite(PIN_TRIG_TRASERO, LOW);

    // Timeout de 6000us (aprox 1 metro) para no bloquear el loop
    long duration = pulseIn(PIN_ECHO_TRASERO, HIGH, 6000);
    if (duration > 0) {
      float lectura_cruda = duration * 0.034f / 2.0f;
      
      // Filtrado de media móvil (reduce ruido)
      historico_distancias[idx_historico] = lectura_cruda;
      idx_historico = (idx_historico + 1) % 5;
      
      // Calcular media móvil de las últimas 5 lecturas válidas
      float suma = 0.0;
      int validos = 0;
      for (int i = 0; i < 5; i++) {
        if (historico_distancias[i] > 0) {
          suma += historico_distancias[i];
          validos++;
        }
      }
      if (validos > 0) {
        distancia_trasera_cm = suma / validos;
      } else {
        distancia_trasera_cm = -1.0;
      }
      
      // Detección de emergencia: detener motores si distancia crítica
      if (distancia_trasera_cm > 0 && distancia_trasera_cm < DISTANCIA_EMERGENCIA_CM) {
        if (velocidadActual != 0) {
          velocidadActual = 0;
          aplicarComandos();  // Detener motores inmediatamente
        }
      }
    } else {
      distancia_trasera_cm = -1.0; // Fuera de rango o error
    }
  }
}
