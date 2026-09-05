#include <Servo.h>
#include <Wire.h>

// ============================================================
// DEFINICIÓN DE PINES
// ============================================================
// Servo de Dirección
const int PIN_SERVO = 9;

// Puente H BTS7960
const int PIN_RPWM = 5; // PWM Derecha (Avanzar)
const int PIN_LPWM = 3; // PWM Izquierda (Retroceder)
const int PIN_R_EN = 7; // Enable Derecha
const int PIN_L_EN = 8; // Enable Izquierda 

// HC-SR04 Trasero
const int PIN_TRIG_TRASERO = 12;
const int PIN_ECHO_TRASERO = 13;

// Constantes de calibración del giroscopio
const int GYRO_BIAS_MUESTRAS = 300;
const float GYRO_DEADBAND_DPS = 1.5f;

// ============================================================
// VARIABLES GLOBALES
// ============================================================
int velocidadActual = 0;
int anguloActual = 90;
String inputString = "";
bool stringComplete = false;

// Variables de sensores
float mpu_z_acumulado = 0.0;
float distancia_trasera_cm = -1.0;
static unsigned long ultimaMedicionUs = 0;
const int MPU_ADDR = 0x68;
static float gyro_z_bias = 0.0f;
static unsigned int ciclo_sensor = 0;
static float historico_distancias[5] = {-1.0, -1.0, -1.0, -1.0, -1.0};
static int idx_historico = 0;
const float DISTANCIA_EMERGENCIA_CM = 5.0;

// Variables de control
Servo servoDireccion;
static unsigned long ultimoSensoresMs = 0;
static unsigned long ultimoTelemetriaMs = 0;
const unsigned long SENSORES_INTERVALO_MS = 10;
const unsigned long TELEMETRIA_INTERVALO_MS = 100;

// ============================================================
// INICIALIZACIÓN
// ============================================================
void setup() {
  initComunicacion();
  initMotores();
  initSensores();
  
  unsigned long ahora = millis();
  ultimoSensoresMs = ahora;
  ultimoTelemetriaMs = ahora;
}

// ============================================================
// LOOP PRINCIPAL
// ============================================================
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

  unsigned long ahora = millis();

  // Lazo de sensores a frecuencia fija
  if (ahora - ultimoSensoresMs >= SENSORES_INTERVALO_MS) {
    ultimoSensoresMs = ahora;
    actualizarSensores();
  }

  // Transmisión de telemetría a frecuencia fija
  if (ahora - ultimoTelemetriaMs >= TELEMETRIA_INTERVALO_MS) {
    ultimoTelemetriaMs = ahora;
    enviarTelemetria();
  }
}

// ============================================================
// COMUNICACIÓN SERIAL
// ============================================================
void initComunicacion() {
  Serial.begin(115200);
  inputString.reserve(50);
}

void chequearSerial() {
  while (Serial.available() && !stringComplete) {
    char inChar = (char)Serial.read();
    inputString += inChar;
    if (inChar == '\n') {
      stringComplete = true;
    }
  }
}

void parsearComando(String comando) {
  comando.trim();
  
  int idxV = comando.indexOf("V:");
  int idxA = comando.indexOf(";A:");
  
  if (idxV != -1 && idxA != -1) {
    String velStr = comando.substring(idxV + 2, idxA);
    String angStr = comando.substring(idxA + 3);
    
    int nuevaVel = velStr.toInt();
    int nuevoAng = angStr.toInt();
    
    if (nuevaVel == 0 && velStr != "0" && velStr != "0\r") return;
    if (nuevoAng == 0 && angStr != "0" && angStr != "0\r") return;
    
    velocidadActual = nuevaVel;
    anguloActual = nuevoAng;
  }
}

void enviarTelemetria() {
  Serial.print("T:Z:");
  Serial.print(mpu_z_acumulado, 1);
  Serial.print(";A:");
  Serial.print(anguloActual);
  Serial.print(";U:");
  Serial.print(distancia_trasera_cm);
  Serial.println(";");
}

// ============================================================
// CONTROL DE MOTORES
// ============================================================
void initMotores() {
  servoDireccion.attach(PIN_SERVO);
  servoDireccion.write(anguloActual);
  
  pinMode(PIN_RPWM, OUTPUT);
  pinMode(PIN_LPWM, OUTPUT);
  pinMode(PIN_R_EN, OUTPUT);
  pinMode(PIN_L_EN, OUTPUT);
  
  digitalWrite(PIN_R_EN, HIGH);
  digitalWrite(PIN_L_EN, HIGH);
  
  analogWrite(PIN_RPWM, 0);
  analogWrite(PIN_LPWM, 0);
}

void aplicarComandos() {
  int anguloSeguro = constrain(anguloActual, 40, 140);
  servoDireccion.write(anguloSeguro);
  
  if (velocidadActual == 0) {
    analogWrite(PIN_RPWM, 0);
    analogWrite(PIN_LPWM, 0);
  } else {
    int velPct = constrain(velocidadActual, -100, 100);
    int pwmOut = map(abs(velPct), 0, 100, 0, 255);
    bool reversa = velPct < 0;
    
    if (reversa) {
      analogWrite(PIN_RPWM, 0);
      analogWrite(PIN_LPWM, pwmOut);
    } else {
      analogWrite(PIN_RPWM, pwmOut);
      analogWrite(PIN_LPWM, 0);
    }
  }
}

// ============================================================
// SENSORES (MPU6050 + HC-SR04)
// ============================================================
void initSensores() {
  pinMode(PIN_TRIG_TRASERO, OUTPUT);
  pinMode(PIN_ECHO_TRASERO, INPUT);
  digitalWrite(PIN_TRIG_TRASERO, LOW);

  Wire.begin();
  Wire.beginTransmission(MPU_ADDR);
  Wire.write(0x6B);
  Wire.write(0);
  Wire.endTransmission(true);

  // Calibración de bias del eje Z
  long suma_z = 0;
  for (int i = 0; i < GYRO_BIAS_MUESTRAS; i++) {
    Wire.beginTransmission(MPU_ADDR);
    Wire.write(0x47);
    Wire.endTransmission(false);
    Wire.requestFrom(MPU_ADDR, 2, true);
    if (Wire.available() == 2) {
      int16_t raw = Wire.read() << 8 | Wire.read();
      suma_z += raw;
    }
    delay(5);
  }
  gyro_z_bias = (float)suma_z / (float)GYRO_BIAS_MUESTRAS / 131.0f;

  ultimaMedicionUs = micros();
}

void actualizarSensores() {
  unsigned long ahoraUs = micros();
  unsigned long deltaUs = ahoraUs - ultimaMedicionUs;
  if (deltaUs == 0) return;

  Wire.beginTransmission(MPU_ADDR);
  Wire.write(0x47);
  Wire.endTransmission(false);
  Wire.requestFrom(MPU_ADDR, 2, true);

  if (Wire.available() == 2) {
    int16_t gyroZ = Wire.read() << 8 | Wire.read();
    float gyroZ_deg_s = ((float)gyroZ / 131.0f) - gyro_z_bias;

    if (abs(gyroZ_deg_s) < GYRO_DEADBAND_DPS) {
      gyroZ_deg_s = 0.0f;
    }

    float deltaSegundos = (float)deltaUs / 1000000.0f;
    mpu_z_acumulado += gyroZ_deg_s * deltaSegundos;
  }

  ultimaMedicionUs = ahoraUs;

  // Lectura HC-SR04 cada 5 ciclos
  ciclo_sensor++;
  if (ciclo_sensor >= 5) {
    ciclo_sensor = 0;
    digitalWrite(PIN_TRIG_TRASERO, HIGH);
    delayMicroseconds(10);
    digitalWrite(PIN_TRIG_TRASERO, LOW);

    long duration = pulseIn(PIN_ECHO_TRASERO, HIGH, 6000);
    if (duration > 0) {
      float lectura_cruda = duration * 0.034f / 2.0f;
      
      historico_distancias[idx_historico] = lectura_cruda;
      idx_historico = (idx_historico + 1) % 5;
      
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
      
      // Detección de emergencia
      if (distancia_trasera_cm > 0 && distancia_trasera_cm < DISTANCIA_EMERGENCIA_CM) {
        if (velocidadActual != 0) {
          velocidadActual = 0;
          aplicarComandos();
        }
      }
    } else {
      distancia_trasera_cm = -1.0;
    }
  }
}
