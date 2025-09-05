/*
 * ============================================================================
 * Arquivo: destra_protocol.ino
 * Autor: Sandro Fadiga
 * Instituição: EESC - USP (Escola de Engenharia de São Carlos)
 * Projeto: DESTRA - DEpurador de Sistemas em Tempo ReAl
 * Data de Criação: 09/01/2025
 * Versão: 1.0
 * 
 * Descrição:
 *   Implementação do protocolo DESTRA para Arduino.
 *   Este arquivo contém toda a lógica de comunicação serial para
 *   operações peek/poke, permitindo leitura e escrita de memória
 *   em tempo real para depuração de sistemas embarcados.
 * 
 * Protocolo:
 *   - Palavras mágicas: 0xCA 0xFE
 *   - Comandos: PEEK (0xF1), POKE (0xF2)
 *   - Endereçamento: 16 bits (0x0100 - 0x08FF para Arduino Uno)
 *   - Tamanho de dados: 1-8 bytes por operação
 *   - Comunicação: Serial 115200 baud, 8N1
 * 
 * Funcionalidades:
 *   - destraSetup(): Inicializa a comunicação serial
 *   - destraHandler(): Processa comandos recebidos (não bloqueante)
 *   - processPeekRequest(): Lê dados da memória
 *   - processPokeRequest(): Escreve dados na memória
 *   - Máquina de estados para parsing de comandos
 *   - Validação de endereços e tamanhos
 *   - Echo de confirmação para todos os bytes recebidos
 * 
 * Formato dos Pacotes:
 *   PEEK: [0xCA][0xFE][0xF1][ADDR_L][ADDR_H][SIZE]
 *   POKE: [0xCA][0xFE][0xF2][ADDR_L][ADDR_H][SIZE][DATA...]
 * 
 * Códigos de Status:
 *   - 0x00: Sucesso
 *   - 0x01: Erro de faixa de endereço
 *   - 0x02: Erro de tamanho
 * 
 * Requisitos:
 *   - Arduino Uno ou compatível
 *   - Memória RAM acessível: 0x0100 - 0x08FF
 * 
 * Uso:
 *   1. Incluir este arquivo no projeto Arduino
 *   2. Chamar destraSetup() no setup()
 *   3. Chamar destraHandler() no loop()
 * 
 * Licença: MIT
 * ============================================================================
 */

#include <Arduino.h>

// Serial communication constants
#define SERIAL_START_MARKER 0xCAFE
#define CMD_PEEK 0xF1
#define CMD_POKE 0xF2
#define STATUS_SUCCESS 0x00
#define STATUS_ADDRESS_RANGE_ERROR 0x01
#define STATUS_SIZE_ERROR 0x02
#define BAUD_RATE 115200
#define BUFFER_SIZE 64 // Buffer for incoming data

// Serial state machine states
enum DestraState {
  WAIT_START_HIGH,
  WAIT_START_LOW,
  WAIT_COMMAND,
  WAIT_ADDRESS_LOW,
  WAIT_ADDRESS_HIGH,
  WAIT_SIZE,
  WAIT_VALUE,
  PROCESS_REQUEST
};

// Serial communication variables
DestraState destraState = WAIT_START_HIGH;
uint8_t destraCommand = 0;
uint16_t destraAddress = 0;  // 16-bit address
uint8_t destraSize = 0;
uint8_t addressLow = 0;
uint8_t addressHigh = 0;
uint8_t destraValueBuffer[8];  // Buffer for POKE value bytes
uint8_t destraValueIndex = 0;   // Index for value buffer


// Place me at the begining of your setup()
void destraSetup() {
  // Initialize serial communication
  Serial.begin(BAUD_RATE);
  // Wait for serial port to connect (needed for native USB boards)
  while (!Serial) {
    ; // Wait for serial port to connect
  }
  destraState = WAIT_START_HIGH;
  Serial.println("Destra is ready...");
}

// Place me at the begining of your loop()
void destraHandler() {
// Function to handle destra serial communication (non-blocking)
  while (Serial.available() > 0 && destraState != PROCESS_REQUEST) {
    uint8_t inByte = Serial.read();
  
    //buffer[bufferIndex] = incomingByte;
    //bufferIndex = (bufferIndex + 1) % BUFFER_SIZE;

    // Packet / Request State Machine     
    switch (destraState) {
      // PEEK/POKE Packet starts with 0xCAFE
      case WAIT_START_HIGH:
        if (inByte == 0xCA) {
          int bytesAvailable = Serial.availableForWrite();
          destraState = WAIT_START_LOW;
          Serial.write(inByte);
        }
        break;
        
      case WAIT_START_LOW:
        if (inByte == 0xFE) {
          destraState = WAIT_COMMAND;
          Serial.write(inByte);
        } else {
          destraState = WAIT_START_HIGH;
        }
        break;
        
      case WAIT_COMMAND:
        destraCommand = inByte;
        if (inByte == CMD_PEEK || inByte == CMD_POKE) {
          destraState = WAIT_ADDRESS_LOW;
          Serial.write(inByte);
        } else {
          destraState = WAIT_START_HIGH;
        }
        break;
        
      case WAIT_ADDRESS_LOW:
        addressLow = inByte;
        Serial.write(inByte);
        destraState = WAIT_ADDRESS_HIGH;
        break;
        
      case WAIT_ADDRESS_HIGH:
        addressHigh = inByte;
        Serial.write(inByte);
        // Combine to 16-bit address (little endian)
        destraAddress = addressLow | (addressHigh << 8);
        destraState = WAIT_SIZE;
        break;
        
      case WAIT_SIZE:
        destraSize = inByte;
        Serial.write(inByte);
        if (destraCommand == CMD_PEEK) {
          destraState = PROCESS_REQUEST;
        }
        else if (destraCommand == CMD_POKE) {
          destraValueIndex = 0;  // Reset value buffer index
          destraState = WAIT_VALUE;
        }
        else {
          destraState = WAIT_START_HIGH;
        }
        break;

      case WAIT_VALUE:
        // Store the value byte
        destraValueBuffer[destraValueIndex] = inByte;
        Serial.write(inByte);  // Echo back
        destraValueIndex++;
        
        // Check if we've received all value bytes
        if (destraValueIndex >= destraSize) {
          destraState = PROCESS_REQUEST;
        }
        // Otherwise stay in WAIT_VALUE to collect more bytes
        break;
    }
  }
  
  // Process the request if we have a complete message
  if (destraState == PROCESS_REQUEST) {
    if (destraCommand == CMD_PEEK) {
      processPeekRequest();
    } else if (destraCommand == CMD_POKE) {
      processPokeRequest();
    }
    destraState = WAIT_START_HIGH;  // Reset for next request
  }
}


// Function to process peek request and send response
void processPeekRequest() {
  // Send response header
  Serial.write(0xCA);
  Serial.write(0xFE);
  Serial.write(CMD_PEEK);
  
  // Validate address range (optional safety check)
  if (destraAddress < 0x100 || destraAddress > 0x8FF) {  // Arduino Uno RAM range
    Serial.write(STATUS_ADDRESS_RANGE_ERROR);
    return;
  }

  // Validate size
  if (destraSize == 0 || destraSize > 8) {
    Serial.write(STATUS_SIZE_ERROR);
    return;
  }
  
  Serial.write(STATUS_SUCCESS);
  
  // Read and send the requested data
  // uint8_t* ptr = (uint8_t*)peekAddress;
  uint8_t* ptr = (uint8_t*)destraAddress;
  for (uint8_t i = 0; i < destraSize; i++) {
    Serial.write(ptr[i]);
  }
}


// Function to process poke request and send response
void processPokeRequest() {
  // Send response header
  Serial.write(0xCA);
  Serial.write(0xFE);
  Serial.write(CMD_POKE);
  
  // Validate address range
  if (destraAddress < 0x100 || destraAddress > 0x8FF) {  // Arduino Uno RAM range
    Serial.write(STATUS_ADDRESS_RANGE_ERROR);
    return;
  }

  // Validate size (already checked in state machine, but double-check)
  if (destraSize == 0 || destraSize > 8) {
    Serial.write(STATUS_SIZE_ERROR);
    return;
  }
  
  // Write the data to memory
  uint8_t* ptr = (uint8_t*)destraAddress;
  for (uint8_t i = 0; i < destraSize; i++) {
    ptr[i] = destraValueBuffer[i];
  }
  
  // Send success status
  Serial.write(STATUS_SUCCESS);
  
  // Optionally, echo back the written data for verification
  // This helps confirm the write was successful
  for (uint8_t i = 0; i < destraSize; i++) {
    Serial.write(ptr[i]);  // Read back from memory and send
  }
}
