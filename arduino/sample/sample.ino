/*
 * ============================================================================
 * Arquivo: sample.ino
 * Autor: Sandro Fadiga
 * Instituição: EESC - USP (Escola de Engenharia de São Carlos)
 * Projeto: DESTRA - DEpurador de Sistemas em Tempo ReAl
 * Data de Criação: 09/01/2025
 * Versão: 1.0
 * 
 * Descrição:
 *   Exemplo simples de uso do protocolo DESTRA em Arduino.
 *   Demonstra como integrar o protocolo de depuração em tempo real
 *   com variáveis de teste para operações peek/poke.
 * 
 * Funcionalidades:
 *   - Inicialização do protocolo DESTRA
 *   - Variáveis de teste (rtc, k_pi, k_radius, etc.)
 *   - Contador RTC incrementado a cada 100ms
 *   - Cálculos demonstrativos com as variáveis
 *   - Handler para processar comandos peek/poke
 * 
 * Variáveis de Teste:
 *   - rtc: Contador de tempo real (unsigned long)
 *   - k_pi: Constante PI (float)
 *   - k_radius: Raio para cálculos (int)
 *   - a_result: Resultado de área do círculo (float)
 *   - a_other_result: Resultado secundário (float)
 * 
 * Requisitos:
 *   - Arduino Uno ou compatível
 *   - Arquivo destra_protocol.ino no mesmo diretório
 * 
 * Uso:
 *   1. Fazer upload para o Arduino
 *   2. Conectar via serial (115200 baud)
 *   3. Usar aplicação DESTRA para peek/poke das variáveis
 * 
 * Licença: MIT
 * ============================================================================
 */

#include <Arduino.h>

// TEST DATA (volatile guarantees that the variable will be at .elf)
volatile unsigned long rtc = 0;
volatile float k_pi = 3.14f;
volatile int k_radius = 3;
volatile float a_result;
volatile float a_other_result;

void setup() {
  destraSetup(); // start serial and destra
}

void loop() {

  destraHandler(); // execute peek and poke commands

  a_result = k_pi * (k_radius * k_radius);
  a_other_result = 2 * rtc;
  
  //rtc += 1;
  // Slow down the counter for easier monitoring
  static unsigned long lastUpdate = 0;
  if (millis() - lastUpdate > 100) {  // Update every 100ms
      rtc += 1;
      lastUpdate = millis();
  }

}
