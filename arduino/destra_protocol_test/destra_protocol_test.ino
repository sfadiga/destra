/*
 * ============================================================================
 * Arquivo: destra_protocol_test.ino
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


// ============================================================================
// DEFINICOES E VARIAVEIS PARA ANALISE - INSTRUMENTACAO PROTOCOLO
// ============================================================================
// Comando especial para recuperar logs de performance
#define CMD_GET_PERF_LOG 0xF3

// VARIÁVEIS DE PERFORMANCE
volatile unsigned long frameCounter = 0;        // Contador de frames
volatile uint16_t frameRate = 0;                // Frame rate de execução
volatile uint16_t frameJitter = 0;              // Jitter de processamento do loop
volatile uint16_t commandSequence = 0;          // Identifica o comando
volatile unsigned long commandStartCounter = 0; // Contador de frame inicio do comando, 0 se não houver comando
volatile unsigned long commandEndCounter = 0;   // Contador de frame do fim do comando, 0 se não houver comando
volatile unsigned long lastFrameTime = 0;       // Tempo do inicio do frame anterior
volatile unsigned long commandReceiveTime = 0;  // Tempo de recepção do comando
volatile unsigned long commandProcessTime = 0;  // Tempo de processamento
volatile unsigned long lastDeltaTime = 0;       // Ultimo delta de tempo calculado

// PINOS DE DEBUG PARA OSCILOSCÓPIO
#define PIN_TRIGGER_RX 2    // Pulso quando recebe comando
#define PIN_TRIGGER_TX 3    // Pulso quando envia resposta
#define PIN_FRAME_TOGGLE 4  // Toggle a cada loop()
#define PIN_BUSY 5          // Alto durante processamento

// Macros para facilitar uso dos pinos de debug
#define PULSE_RX() { digitalWrite(PIN_TRIGGER_RX, HIGH);  delayMicroseconds(10);  digitalWrite(PIN_TRIGGER_RX, LOW); }
#define PULSE_TX() { digitalWrite(PIN_TRIGGER_TX, HIGH);  delayMicroseconds(10);  digitalWrite(PIN_TRIGGER_TX, LOW); }
#define TOGGLE_FRAME() { digitalWrite(PIN_FRAME_TOGGLE, !digitalRead(PIN_FRAME_TOGGLE)); }
#define SET_BUSY(state) { digitalWrite(PIN_BUSY, state); }

// ESTRUTURA E BUFFER DE PERFORMANCE
#define PERF_BUFFER_SIZE 100
struct PerfLog
{
  unsigned long frameCounter;        // Contador absoluto de frames
  uint16_t frameRate;                // Frame rate
  uint16_t frameJitter;              // Diferença entre frames consecutivos
  uint16_t commandSequence;          // Identifica o comando
  uint16_t commandFrameCounterDelta; // Distancia do frame executado do frame de inicio do comando, 0 se mesmo frame
  unsigned long commandProcessTime;  // Tempo de execução do comando atual, 0 se não houver comando
};
PerfLog perfBuffer[PERF_BUFFER_SIZE];
uint8_t perfIndex = 0;
// ============================================================================
// FIM - DEFINICOES E VARIAVEIS PARA ANALISE - INSTRUMENTACAO PROTOCOLO
// ============================================================================


// ============================================================================
// FUNCOES ARDUINO INSTRUMENTADAS - SETUP  E LOOP
// ============================================================================
void setup() {
    // inicializar Teste
    destraTestSetup();
    // Inicializar DESTRA
    destraSetup();
}

void loop() {
  unsigned long currentFrameTime = micros();
  unsigned long deltaTime = currentFrameTime - lastFrameTime;  // duração do frame anterior

  // Calcular framerate (Hz)
  if (deltaTime > 0) {
    frameRate = 1000000.0 / deltaTime;
  }

  // Calcular jitter (diferença absoluta entre períodos consecutivos)
  frameJitter = abs((long)deltaTime - (long)lastDeltaTime);
  lastDeltaTime = deltaTime;

  // Toggle do pino de frame
  TOGGLE_FRAME();
  frameCounter++;

  // Processar comandos DESTRA
  destraHandler();

  // Executar cálculos de exemplo
  calculation();

  // Ajustar para ~100Hz (10ms)
  unsigned long elapsed = micros() - currentFrameTime;
  if (elapsed < 10000) {
    delayMicroseconds(10000 - elapsed);
  }

  lastFrameTime = currentFrameTime;
}

// Usaer em conjunto com Destra Setup 
void destraTestSetup() {
  // Configurar pinos de debug
  pinMode(PIN_TRIGGER_RX, OUTPUT);
  pinMode(PIN_TRIGGER_TX, OUTPUT);
  pinMode(PIN_FRAME_TOGGLE, OUTPUT);
  pinMode(PIN_BUSY, OUTPUT);

  // Inicializar pinos em LOW
  digitalWrite(PIN_TRIGGER_RX, LOW);
  digitalWrite(PIN_TRIGGER_TX, LOW);
  digitalWrite(PIN_FRAME_TOGGLE, LOW);
  digitalWrite(PIN_BUSY, LOW);
}

// Destra Setup Original
void destraSetup() {
  // Inicializar comunicação serial
  Serial.begin(BAUD_RATE);
  // Aguardar conexão da porta serial (necessário para placas USB nativas)
  while (!Serial) {
    ; // Aguardar conexão da porta serial
  }
  destraState = WAIT_START_HIGH;
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
          
          // // INTRUMENTAÇÃO - Pulso RX no primeiro byte de um novo comando
          PULSE_RX();
          commandReceiveTime = micros();
          commandStartCounter = frameCounter;
          SET_BUSY(HIGH);

        }
        break;
        
      case WAIT_START_LOW:
        if (inByte == 0xFE) {
          destraState = WAIT_COMMAND;
        } else {
          destraState = WAIT_START_HIGH;
          SET_BUSY(LOW); // INTRUMENTAÇÃO
        }
        break;
        
      case WAIT_COMMAND:
        destraCommand = inByte;
        if (inByte == CMD_PEEK || inByte == CMD_POKE) {
          destraState = WAIT_ADDRESS_LOW;
        } 
        else if (inByte == CMD_GET_PERF_LOG) {
          destraState = PROCESS_REQUEST;
        } 
        else {
          destraState = WAIT_START_HIGH;
          SET_BUSY(LOW); // INTRUMENTAÇÃO
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
          SET_BUSY(LOW); // INTRUMENTAÇÃO
        }
        break;

      case WAIT_VALUE:
        // Verificar se o índice está dentro dos limites do buffer
        if (destraValueIndex < 8 && destraValueIndex < destraSize) {
          // Armazenar o byte de valor
          destraValueBuffer[destraValueIndex] = inByte;
          destraValueIndex++;
        }
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
    else if (destraCommand == CMD_GET_PERF_LOG) {
      processGetPerfLog();
    }
    destraCommand = 0;
    destraState = WAIT_START_HIGH;  // Resetar para próxima requisição

    // INTRUMENTAÇÃO - Registrar tempo de processamento
    SET_BUSY(LOW);
    commandEndCounter = frameCounter;
    commandProcessTime = micros() - commandReceiveTime;
    commandSequence++;
    registerPerformanceStats();
  }
}


// Função para processar requisição peek e enviar resposta
void processPeekRequest() {
  // INTRUMENTAÇÃO - Pulso TX antes de enviar resposta
  PULSE_TX();

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
  // INTRUMENTAÇÃO - Pulso TX antes de enviar resposta
  PULSE_TX();
    
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

// INTRUMENTAÇÃO - Funcao para processar a requisicao de performance e enviar resposta
void sendPerfLogEntry(const PerfLog& e) {
    Serial.write((uint8_t*)&e.frameCounter, 4);
    Serial.write((uint8_t*)&e.frameRate, 2);
    Serial.write((uint8_t*)&e.frameJitter, 2);
    Serial.write((uint8_t*)&e.commandSequence, 2);
    Serial.write((uint8_t*)&e.commandFrameCounterDelta, 2);
    Serial.write((uint8_t*)&e.commandProcessTime, 4);
}

void processGetPerfLog() {
    // Cabeçalho
    Serial.write(0xCA);
    Serial.write(0xFE);
    Serial.write(CMD_GET_PERF_LOG);
    Serial.write(STATUS_SUCCESS);

    // Número de entradas
    Serial.write(perfIndex);

    // Payload
    for (uint8_t i = 0; i < perfIndex; i++) {
        sendPerfLogEntry(perfBuffer[i]);
    }

    // Reset
    perfIndex = 0;
}

// INTRUMENTAÇÃO - Função para REGISTRAR ESTATÍSTICAS DE PERFORMANCE
void registerPerformanceStats() {
  if (perfIndex < 99) {
    perfBuffer[perfIndex] = { frameCounter, frameRate, frameJitter, commandSequence, (uint16_t)(commandEndCounter-commandStartCounter), commandProcessTime };
    perfIndex = (perfIndex + 1) % PERF_BUFFER_SIZE;
  }
}
