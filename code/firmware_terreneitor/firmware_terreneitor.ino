#include <Servo.h>
// #include <Wire.h>  // Comentado: Deshabilitado MPU6050 - El sensor MPU ha sido deshabilitado completamente

// ============================================================
// DEFINICIÓN DE PINES
// ============================================================
// Servo de Dirección
const int PIN_SERVO = 9;

// Servo de Ultrasónico (paneo)
const int PIN_SERVO_ULTRASONICO = 10;

// Puente H BTS7960
const int PIN_RPWM = 5; // PWM Derecha (Avanzar)
const int PIN_LPWM = 3; // PWM Izquierda (Retroceder)
const int PIN_R_EN = 7; // Enable Derecha
const int PIN_L_EN = 8; // Enable Izquierda 

// HC-SR04 Frontal
const int PIN_TRIG_FRONTAL = 11;
const int PIN_ECHO_FRONTAL = 12;

// Constantes de calibración del giroscopio
// const int GYRO_BIAS_MUESTRAS = 300;  // Comentado: Deshabilitado MPU6050
// const float GYRO_DEADBAND_DPS = 1.5f;  // Comentado: Deshabilitado MPU6050

// ============================================================
// VARIABLES GLOBALES
// ============================================================
int velocidadActual = 0;
int anguloActual = 90;
String inputString = "";
bool stringComplete = false;

// Variables de sensores
float distancia_frontal_cm = -1.0;
static unsigned long ultimaMedicionUs = 0;

// Variables de control
Servo servoDireccion;
Servo servoUltrasonico;
static unsigned long ultimoSensoresMs = 0;
static unsigned long ultimoTelemetriaMs = 0;
const unsigned long SENSORES_INTERVALO_MS = 10;
const unsigned long TELEMETRIA_INTERVALO_MS = 100;

// Ángulos predefinidos para servo de dirección (rango completo SG90: 0-180°)
const int ANGULO_CENTRO = 90;
const int ANGULO_DERECHA = 0;    // Extrema derecha
const int ANGULO_IZQUIERDA = 180; // Extrema izquierda

// Ángulos predefinidos para servo de ultrasónico (paneo)
const int ANGULO_SERVO_CENTRO = 50;
const int ANGULO_SERVO_IZQUIERDA = 100;
const int ANGULO_SERVO_DERECHA = 0;

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
  
  // Comandos simples de dirección (un solo carácter)
  if (comando.length() == 1) {
    char cmd = comando.charAt(0);
    switch (cmd) {
      case 'C':
        anguloActual = ANGULO_CENTRO;
        Serial.println("Comando: CENTRAR");
        return;
      case 'D':
        anguloActual = ANGULO_DERECHA;
        Serial.println("Comando: DERECHA");
        return;
      case 'I':
        anguloActual = ANGULO_IZQUIERDA;
        Serial.println("Comando: IZQUIERDA");
        return;
      case 'S':
        servoUltrasonico.write(ANGULO_SERVO_CENTRO);
        Serial.println("Comando: SERVO CENTRO");
        return;
      case 'L':
        servoUltrasonico.write(ANGULO_SERVO_IZQUIERDA);
        Serial.println("Comando: SERVO IZQUIERDA");
        return;
      case 'R':
        servoUltrasonico.write(ANGULO_SERVO_DERECHA);
        Serial.println("Comando: SERVO DERECHA");
        return;
    }
  }
  
  // Comando tradicional V:vel;A:ang (mantener compatibilidad)
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
  Serial.print("D:");
  Serial.print(distancia_frontal_cm, 1);
  Serial.println(";");
}

// ============================================================
// CONTROL DE MOTORES
// ============================================================
void initMotores() {
  servoDireccion.attach(PIN_SERVO);
  servoDireccion.write(anguloActual);
  
  servoUltrasonico.attach(PIN_SERVO_ULTRASONICO);
  servoUltrasonico.write(ANGULO_SERVO_CENTRO);
  
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
  int anguloSeguro = constrain(anguloActual, 0, 180); // Rango completo SG90
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
// SENSORES (HC-SR04 Frontal)
// ============================================================
void initSensores() {
  pinMode(PIN_TRIG_FRONTAL, OUTPUT);
  pinMode(PIN_ECHO_FRONTAL, INPUT);
  digitalWrite(PIN_TRIG_FRONTAL, LOW);
}

void actualizarSensores() {
  // Leer ultrasónico frontal
  digitalWrite(PIN_TRIG_FRONTAL, HIGH);
  delayMicroseconds(10);
  digitalWrite(PIN_TRIG_FRONTAL, LOW);

  long duration_frontal = pulseIn(PIN_ECHO_FRONTAL, HIGH, 30000);
  if (duration_frontal > 0) {
    distancia_frontal_cm = duration_frontal * 0.034f / 2.0f;
  } else {
    distancia_frontal_cm = -1.0;
  }
}
