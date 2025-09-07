# DESTRA - DEpurador de Sistemas em Tempo ReAl

**Projeto desenvolvido para o Curso de Especialização em Sistemas Aeronáuticos (2024)**  
**EESC - USP (Escola de Engenharia de São Carlos)**

## Resumo

O DESTRA é uma ferramenta de depuração em tempo real para sistemas embarcados, implementando um protocolo de comunicação peek/poke através de interface serial. Esta solução, amplamente utilizada na indústria aeroespacial e de sistemas críticos, permite a inspeção e modificação de variáveis em memória durante a execução do sistema, sem interrupção do fluxo de operação.

## Motivação

Embora mecanismos de depuração peek/poke sejam amplamente utilizados na indústria, não existe padronização ou normalização estabelecida. Cada organização implementa soluções proprietárias considerando requisitos específicos de segurança, desempenho e arquitetura do hardware alvo.

Este projeto propõe uma implementação padronizada de um mecanismo request/response que estabelece uma camada de comunicação entre um host externo e o sistema embarcado. O protocolo permite:

- **Peek (espiar)**: Requisição para leitura do valor de uma variável em endereço específico de memória
- **Poke (modificar)**: Requisição para escrita de um novo valor em endereço específico de memória

Esta abordagem viabiliza validações e verificações de requisitos durante a fase de integração de sistemas, particularmente em cenários onde o acesso ao hardware interno é limitado e os testes devem ser realizados com o sistema operando em tempo real.

## Especificação do Protocolo

### Estrutura do Protocolo

O protocolo consiste em uma sequência de bytes transmitida via interface serial, interpretada tanto pela ferramenta host quanto pelo software embarcado. A implementação abstrai os detalhes do protocolo, dispensando o envolvimento direto do usuário no processamento dos pacotes.

### Formato do Pacote

#### Estrutura Base
```
[PALAVRA_MÁGICA][COMANDO][ENDEREÇO][TAMANHO][DADOS_OPCIONAIS]
```

- **Palavra Mágica**: `0xCAFE` (2 bytes) - Identificador único do protocolo
- **Comando**: 1 byte
  - `0xF1`: Comando PEEK
  - `0xF2`: Comando POKE
- **Endereço**: 2 bytes (16 bits) - Endereço de memória em formato little-endian
- **Tamanho**: 1 byte - Quantidade de bytes a serem lidos/escritos (1-8 bytes)
- **Dados**: N bytes - Presente apenas em comandos POKE

### Endianness e Ordenação de Bytes

O protocolo utiliza **little-endian** para transmissão de valores multi-byte, mantendo compatibilidade nativa com a arquitetura AVR do Arduino UNO. Esta escolha elimina overhead de conversão no microcontrolador, otimizando o desempenho.

#### Exemplo de Comando PEEK

Para a variável `k_radius` com endereço `0x0104`, tipo `int16` e tamanho 2 bytes:

**Pacote transmitido**: `CA FE F1 04 01 02`

Decomposição:
- `CA FE`: Palavras mágicas
- `F1`: Comando PEEK
- `04`: Byte baixo do endereço (LSB)
- `01`: Byte alto do endereço (MSB)
- `02`: Tamanho (2 bytes)

Note que o endereço `0x0104` é transmitido como `04 01` (little-endian).

#### Exemplo de Comando POKE

Para a mesma variável `k_radius`, escrevendo o valor 4 (0x0004):

**Pacote transmitido**: `CA FE F2 04 01 02 04 00`

Decomposição:
- `CA FE`: Palavras mágicas
- `F2`: Comando POKE
- `04 01`: Endereço 0x0104 em little-endian
- `02`: Tamanho (2 bytes)
- `04 00`: Valor 0x0004 em little-endian

### Protocolo de Resposta

Ambos os comandos retornam uma resposta estruturada:

```
[PALAVRA_MÁGICA][COMANDO][STATUS][DADOS]
```

- **Status**: 1 byte
  - `0x00`: Sucesso
  - `0x01`: Erro de faixa de endereço
  - `0x02`: Erro de tamanho
- **Dados**: N bytes conforme solicitado (PEEK) ou eco dos dados escritos (POKE)

## Arquitetura do Sistema

### Componentes

O sistema DESTRA é composto por dois componentes principais:

1. **Módulo Embarcado** (`destra_protocol.ino`): Implementação do protocolo para Arduino
2. **Ferramenta Host** (Python): Interface gráfica e processamento de comandos

### Dicionário de Dados

O sistema utiliza arquivos ELF (Executable and Linkable Format) com informações de debug DWARF para extrair automaticamente:
- Endereços de variáveis
- Tipos de dados
- Tamanhos em memória
- Estruturas e arrays

## Estrutura do Projeto

| Diretório | Arquivo | Descrição |
|:----------|:--------|:----------|
| `/` | `README.md` | Documentação do projeto |
| `/` | `LICENSE` | Licença MIT |
| `/` | `run_destra.bat` | Script de inicialização da ferramenta |
| `/arduino/sample/` | `destra_protocol.ino` | Implementação do protocolo para Arduino |
| `/arduino/sample/` | `sample.ino` | Exemplo de integração |
| `/src/` | `data_dictionary.py` | Parser de arquivos ELF/DWARF |
| `/src/` | `destra_ui.py` | Interface gráfica (PySide/Qt) |
| `/src/` | `destra.py` | Implementação do protocolo no host |
| `/src/` | `logger_config.py` | Sistema de logging |
| `/src/` | `requirements.txt` | Dependências Python |

## Guia de Implementação

### Software Embarcado

O protocolo DESTRA foi desenvolvido e otimizado para Arduino UNO (ATmega328P).

#### Integração ao Projeto Arduino

1. **Inclusão do Protocolo**: Copiar `destra_protocol.ino` para o diretório do projeto Arduino.

2. **Inicialização**: Adicionar no início da função `setup()`:
   ```c
   void setup() {
       destraSetup();  // Inicializa protocolo e comunicação serial
       // Resto do código de setup...
   }
   ```

3. **Processamento de Comandos**: Adicionar na função `loop()`:
   ```c
   void loop() {
       destraHandler();  // Processa comandos peek/poke
       // Resto do código do loop...
   }
   ```

4. **Geração do Arquivo ELF**: 
   - Menu: `Sketch → Export Compiled Binary`
   - O arquivo `.elf` contém símbolos de debug necessários para o dicionário de dados

> **Nota**: [ELF - Executable and Linkable Format](https://pt.wikipedia.org/wiki/Executable_and_Linkable_Format) é o formato padrão para executáveis em sistemas Unix-like, contendo código compilado e informações de debug.

### Ferramenta Host (DESTRA UI)

Interface gráfica desenvolvida em Python utilizando PySide6 (Qt for Python).

#### Procedimento de Uso

1. **Inicialização**: Executar `run_destra.bat` (instalação automática de dependências)

2. **Conexão Serial**:
   - Auto-detecção de portas Arduino
   - Seleção manual se múltiplos dispositivos detectados
   - Baudrate: 115200 bps (8N1)

3. **Carregamento do Dicionário de Dados**:
   - Selecionar arquivo `.elf` gerado pela compilação
   - Parsing automático de variáveis via DWARF debug info
   - Filtragem por nome com suporte a wildcards

4. **Seleção de Variáveis**:
   - Duplo clique para adicionar à lista de monitoramento
   - Visualização de endereço, tipo e tamanho

5. **Operações**:
   - **PEEK**: Leitura instantânea do valor atual
   - **POKE**: Escrita de novo valor (duplo clique na célula + entrada de valor)
   - **Auto PEEK**: Monitoramento contínuo com frequência configurável (1-100 Hz)

6. **Gerenciamento**:
   - Remoção de variáveis: duplo clique no nome
   - Níveis de log configuráveis: DEBUG, INFO, WARNING, ERROR

## Considerações Técnicas

### Limitações e Restrições

1. **Largura de Banda Serial**: O throughput máximo é limitado pelo baudrate configurado. Para monitoramento contínuo de múltiplas variáveis, considerar:
   - Taxa de atualização × número de variáveis × tamanho médio do pacote < baudrate

2. **Otimização do Compilador**: Variáveis podem ser otimizadas e removidas do binário final. Recomenda-se:
   ```c
   volatile int variavel_importante;  // Previne otimização
   ```

3. **Posicionamento do Handler**: A localização de `destraHandler()` no loop afeta:
   - **Início do loop**: Captura estado inicial do ciclo
   - **Entre operações**: Permite depuração de estados intermediários
   - **Final do loop**: Captura estado final após processamento

4. **Overhead de Processamento**: Cada operação peek/poke consome aproximadamente:
   - Tempo de transmissão: (6 + tamanho) × 10 / baudrate segundos
   - Processamento no Arduino: ~100-200 μs

5. **Ausência de Controle de Fluxo**: O protocolo não implementa:
   - Retransmissão automática
   - Detecção de perda de pacotes
   - Checksums ou CRC

### Segurança e Boas Práticas

1. **Validação de Endereços**: O protocolo valida faixa de memória RAM (0x0100-0x08FF para Arduino UNO)

2. **Tipos de Dados**: A ferramenta não valida compatibilidade de tipos. Responsabilidade do operador garantir correspondência entre tipo declarado e valor inserido.

3. **Acesso Concorrente**: Operações peek/poke não são atômicas. Em sistemas multi-threaded ou com interrupções, considerar mecanismos de sincronização.

4. **Modo Continuous**: Não implementado. Cada operação requer requisição explícita, prevenindo sobrecarga inadvertida do sistema.

## Extensibilidade e Trabalhos Futuros

### Suporte Multi-Arquitetura

Para extensão a outras arquiteturas além do AVR, considerar:

1. **Detecção Automática de Endianness**: Implementação de handshake inicial para identificação da arquitetura target
2. **Adaptação Dinâmica**: Configuração automática de formatos de dados baseada na plataforma detectada
3. **Abstração de Endereços**: Suporte para espaços de endereçamento maiores que 16 bits

### Melhorias Propostas

- Implementação de checksums/CRC para integridade de dados
- Protocolo de retransmissão para ambientes com ruído
- Suporte para tipos de dados complexos (structs aninhadas, unions)
- Interface para logging e análise temporal de variáveis
- Integração com ferramentas de análise estática

## Conclusão

O DESTRA oferece uma solução padronizada e eficiente para depuração em tempo real de sistemas embarcados, particularmente adequada para ambientes de desenvolvimento e validação onde o acesso direto ao hardware é limitado. A arquitetura modular e o protocolo bem definido facilitam adaptações para diferentes plataformas e requisitos específicos de projeto.

## Referências

- [Arduino Reference](https://www.arduino.cc/reference/en/)
- [DWARF Debugging Standard](http://dwarfstd.org/)
- [ELF Specification](http://www.skyfree.org/linux/references/ELF_Format.pdf)
- [AVR Instruction Set Manual](http://ww1.microchip.com/downloads/en/devicedoc/atmel-0856-avr-instruction-set-manual.pdf)

## Licença

Este projeto está licenciado sob a Licença MIT - veja o arquivo [LICENSE](LICENSE) para detalhes.

## Autor

**Sandro Fadiga**  
Escola de Engenharia de São Carlos - USP  
Curso de Especialização em Sistemas Aeronáuticos (2024)

---

*Última atualização: Janeiro 2025*
