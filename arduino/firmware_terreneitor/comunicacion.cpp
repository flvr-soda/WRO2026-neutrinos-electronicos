#include "config.h"

void initComunicacion() {
  Serial.begin(115200);
  inputString.reserve(50); // Reservar memoria para evitar fragmentación
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
