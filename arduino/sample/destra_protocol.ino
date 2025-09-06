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

// Constantes de comunicação serial
#define SERIAL_START_MARKER 0xCAFE
#define CMD_PEEK 0xF1
#define CMD_POKE 0xF2
#define STATUS_SUCCESS 0x00
#define STATUS_ADDRESS_RANGE_ERROR 0x01
#define STATUS_SIZE_ERROR 0x02
#define BAUD_RATE 115200
#define BUFFER_SIZE 64 // Buffer para dados recebidos

// Estados da máquina de estados serial
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

// Variáveis de comunicação serial
DestraState destraState = WAIT_START_HIGH;
uint8_t destraCommand = 0;
uint16_t destraAddress = 0;  // Endereço de 16 bits
uint8_t destraSize = 0;
uint8_t addressLow = 0;
uint8_t addressHigh = 0;
uint8_t destraValueBuffer[8];  // Buffer para bytes de valor do POKE
uint8_t destraValueIndex = 0;   // Índice para buffer de valor


// Coloque-me no início do seu setup()
void destraSetup() {
  // Inicializar comunicação serial
  Serial.begin(BAUD_RATE);
  // Aguardar conexão da porta serial (necessário para placas USB nativas)
  while (!Serial) {
    ; // Aguardar conexão da porta serial
  }
  destraState = WAIT_START_HIGH;
  Serial.println("Destra está pronto...");
}

// Coloque-me no início do seu loop()
void destraHandler() {
// Função para lidar com comunicação serial destra (não bloqueante)
  while (Serial.available() > 0 && destraState != PROCESS_REQUEST) {
    uint8_t inByte = Serial.read();
  
    // Máquina de Estados do Pacote/Requisição     
    switch (destraState) {
      // Pacote PEEK/POKE começa com 0xCAFE
      case WAIT_START_HIGH:
        if (inByte == 0xCA) {
          int bytesAvailable = Serial.availableForWrite();
          destraState = WAIT_START_LOW;
        }
        break;
        
      case WAIT_START_LOW:
        if (inByte == 0xFE) {
          destraState = WAIT_COMMAND;
        } else {
          destraState = WAIT_START_HIGH;
        }
        break;
        
      case WAIT_COMMAND:
        destraCommand = inByte;
        if (inByte == CMD_PEEK || inByte == CMD_POKE) {
          destraState = WAIT_ADDRESS_LOW;
        } else {
          destraState = WAIT_START_HIGH;
        }
        break;
        
      case WAIT_ADDRESS_LOW:
        addressLow = inByte;
        destraState = WAIT_ADDRESS_HIGH;
        break;
        
      case WAIT_ADDRESS_HIGH:
        addressHigh = inByte;
        // Combinar para endereço de 16 bits (little endian)
        destraAddress = addressLow | (addressHigh << 8);
        destraState = WAIT_SIZE;
        break;
        
      case WAIT_SIZE:
        destraSize = inByte;
        if (destraCommand == CMD_PEEK) {
          destraState = PROCESS_REQUEST;
        }
        else if (destraCommand == CMD_POKE) {
          destraValueIndex = 0;  // Resetar índice do buffer de valor
          destraState = WAIT_VALUE;
        }
        else {
          destraState = WAIT_START_HIGH;
        }
        break;

      case WAIT_VALUE:
        // Armazenar o byte de valor
        destraValueBuffer[destraValueIndex] = inByte;
        destraValueIndex++;
        // Verificar se recebemos todos os bytes de valor
        if (destraValueIndex >= destraSize) {
          destraState = PROCESS_REQUEST;
        }
        // Caso contrário, permanecer em WAIT_VALUE para coletar mais bytes
        break;
    }
  }
  
  // Processar a requisição se tivermos uma mensagem completa
  if (destraState == PROCESS_REQUEST) {
    if (destraCommand == CMD_PEEK) {
      processPeekRequest();
    } else if (destraCommand == CMD_POKE) {
      processPokeRequest();
    }
    destraState = WAIT_START_HIGH;  // Resetar para próxima requisição
  }
}


// Função para processar requisição peek e enviar resposta
void processPeekRequest() {
  // Enviar cabeçalho da resposta
  Serial.write(0xCA);
  Serial.write(0xFE);
  Serial.write(CMD_PEEK);
  
  // Validar faixa de endereço (verificação de segurança opcional)
  if (destraAddress < 0x100 || destraAddress > 0x8FF) {  // Faixa de RAM do Arduino Uno
    Serial.write(STATUS_ADDRESS_RANGE_ERROR);
    return;
  }

  // Validar tamanho
  if (destraSize == 0 || destraSize > 8) {
    Serial.write(STATUS_SIZE_ERROR);
    return;
  }
  
  Serial.write(STATUS_SUCCESS);
  
  // Ler e enviar os dados solicitados
  uint8_t* ptr = (uint8_t*)destraAddress;
  for (uint8_t i = 0; i < destraSize; i++) {
    Serial.write(ptr[i]);
  }
}


// Função para processar requisição poke e enviar resposta
void processPokeRequest() {
  // Enviar cabeçalho da resposta
  Serial.write(0xCA);
  Serial.write(0xFE);
  Serial.write(CMD_POKE);
  
  // Validar faixa de endereço
  if (destraAddress < 0x100 || destraAddress > 0x8FF) {  // Faixa de RAM do Arduino Uno
    Serial.write(STATUS_ADDRESS_RANGE_ERROR);
    return;
  }

  // Validar tamanho (já verificado na máquina de estados, mas dupla verificação)
  if (destraSize == 0 || destraSize > 8) {
    Serial.write(STATUS_SIZE_ERROR);
    return;
  }
  
  // Escrever os dados na memória
  uint8_t* ptr = (uint8_t*)destraAddress;
  for (uint8_t i = 0; i < destraSize; i++) {
    ptr[i] = destraValueBuffer[i];
  }
  
  // Enviar status de sucesso
  Serial.write(STATUS_SUCCESS);
  
  // Opcionalmente, ecoar de volta os dados escritos para verificação
  // Isso ajuda a confirmar que a escrita foi bem-sucedida
  for (uint8_t i = 0; i < destraSize; i++) {
    Serial.write(ptr[i]);  // Ler de volta da memória e enviar
  }
}
