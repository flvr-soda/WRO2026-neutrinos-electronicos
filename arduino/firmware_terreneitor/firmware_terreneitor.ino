#include <Servo.h>

// Definición de pines
// Servo de Dirección
const int PIN_SERVO = 9;

// Puente H BTS7960
const int PIN_RPWM = 5; // PWM Derecha (Avanzar)
const int PIN_LPWM = 6; // PWM Izquierda (Retroceder)
const int PIN_R_EN = 7; // Enable Derecha
const int PIN_L_EN = 8; // Enable Izquierda

// Variables de hardware
Servo servoDireccion;

// Variables de comunicación
String inputString = "";         // String para almacenar los datos entrantes
bool stringComplete = false;     // Bandera cuando el string está completo

// Estado actual
int velocidadActual = 0;
int anguloActual = 90;

void parsearComando(String comando);
void aplicarComandos();
void chequearSerial();

void setup() {
  // Inicializar puerto serial
  Serial.begin(115200);
  
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
  
  inputString.reserve(50); // Reservar memoria para evitar fragmentación
}

void loop() {
  // Chequear recepción por serial continuamente sin bloquear
  chequearSerial();

  // Procesar comandos seriales si están disponibles sin bloquear
  if (stringComplete) {
    parsearComando(inputString);
    aplicarComandos();
    
    // Limpiar el string para la siguiente lectura
    inputString = "";
    stringComplete = false;
  }
}

void chequearSerial() {
  while (Serial.available() && !stringComplete) {
    char inChar = (char)Serial.read();
    inputString += inChar;
    // Si recibimos salto de línea, el comando está completo
    if (inChar == '\n') {
      stringComplete = true;
    }
  }
}

// Parsea el formato "V:[vel];A:[ang]\n"
void parsearComando(String comando) {
  // Limpiar caracteres de retorno de carro
  comando.trim(); 
  
  int idxV = comando.indexOf("V:");
  int idxA = comando.indexOf(";A:");
  
  if (idxV != -1 && idxA != -1) {
    // Extraer substrings
    String velStr = comando.substring(idxV + 2, idxA);
    String angStr = comando.substring(idxA + 3);
    
    // Convertir a enteros
    velocidadActual = velStr.toInt();
    anguloActual = angStr.toInt();
  }
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
