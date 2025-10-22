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

// ============================================================================
// Configuração de build
// ============================================================================
#define ENABLE_DESTRA_TESTS   // comente esta linha para desativar o módulo de testes
// ============================================================================

#include <Arduino.h>

// TEST DATA (usamos variavaies como volatile para assegurar que estarão no arquivo .elf)
volatile unsigned long rtc = 0;
volatile float k_pi = 3.14f;
volatile uint8_t k_radius = 3;
volatile float result_circle_area;
volatile unsigned long result_rtc_x_radius;

void calculation() {

  // examplos de calculos com variaveis a serem monitoradas / alteradas
  result_circle_area = k_pi * (k_radius * k_radius);
  result_rtc_x_radius = k_radius * rtc;
  rtc += 1;

}

// IMPLEMENTADO NA INSTRUMENTAÇÃO
/* 
void setup()
{
  destraSetup(); // inicializa o protocolo destra (e a serial)
}

void loop()
{
  destraHandler(); // processa e executa peek and poke
  
  // atualiza o calculo a cada 10ms
  if (millis() - lastUpdate > 10)
  {
    calculation();
    lastUpdate = millis();
  }
}
*/