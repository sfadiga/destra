# Diagramas de Sequência - Protocolo DESTRA

## Visão Geral

Este documento apresenta os diagramas de sequência detalhados para as operações PEEK e POKE do protocolo DESTRA, mostrando a interação entre os componentes do sistema.

## Operação PEEK Completa

### Caso de Sucesso

```mermaid
sequenceDiagram
    autonumber
    participant UI as Interface (Python)
    participant Protocol as DestraProtocol
    participant Serial as Serial Port
    participant Arduino as Arduino
    participant RAM as Memória RAM
    
    UI->>Protocol: peek(address=0x0104, size=2)
    Note over Protocol: Valida parâmetros<br/>0 ≤ address ≤ 0xFFFF<br/>1 ≤ size ≤ 8
    
    Protocol->>Protocol: Constrói pacote
    Note right of Protocol: [0xCA][0xFE][0xF1]<br/>[0x04][0x01][0x02]
    
    Protocol->>Serial: write(6 bytes)
    Serial->>Arduino: Transmite bytes
    
    loop Para cada byte recebido
        Arduino->>Arduino: Máquina de estados<br/>processa byte
    end
    
    Note over Arduino: Estado: PROCESS_REQUEST<br/>Comando: PEEK
    
    Arduino->>Arduino: Valida endereço<br/>0x0100 ≤ 0x0104 ≤ 0x08FF
    
    Arduino->>RAM: Lê 2 bytes em 0x0104
    RAM-->>Arduino: Retorna dados [0x12, 0x34]
    
    Arduino->>Arduino: Constrói resposta
    Note right of Arduino: [0xCA][0xFE][0xF1]<br/>[0x00][0x12][0x34]
    
    Arduino->>Serial: write(6 bytes)
    Serial->>Protocol: read(6 bytes)
    
    Protocol->>Protocol: Valida resposta
    Note over Protocol: Verifica palavra mágica<br/>Verifica comando<br/>Verifica status
    
    Protocol->>Protocol: Decodifica dados
    Note right of Protocol: bytes [0x12, 0x34]<br/>→ int16: 0x3412<br/>(little-endian)
    
    Protocol-->>UI: Retorna valor decodificado
    UI->>UI: Atualiza display
```

### Caso de Erro - Endereço Inválido

```mermaid
sequenceDiagram
    autonumber
    participant UI as Interface (Python)
    participant Protocol as DestraProtocol
    participant Serial as Serial Port
    participant Arduino as Arduino
    
    UI->>Protocol: peek(address=0x1000, size=2)
    Note over Protocol: Endereço fora da RAM
    
    Protocol->>Protocol: Constrói pacote
    Protocol->>Serial: write(6 bytes)
    Serial->>Arduino: [0xCA][0xFE][0xF1][0x00][0x10][0x02]
    
    Arduino->>Arduino: Processa comando
    Note over Arduino: Valida endereço<br/>0x1000 > 0x08FF ❌
    
    Arduino->>Serial: Envia erro
    Note right of Arduino: [0xCA][0xFE][0xF1]<br/>[0x01] (ADDRESS_ERROR)
    
    Serial->>Protocol: read(4 bytes)
    Protocol->>Protocol: Detecta erro
    
    Protocol-->>UI: Retorna None
    UI->>UI: Exibe mensagem de erro
```

## Operação POKE Completa

### Caso de Sucesso

```mermaid
sequenceDiagram
    autonumber
    participant UI as Interface (Python)
    participant Protocol as DestraProtocol
    participant Serial as Serial Port
    participant Arduino as Arduino
    participant RAM as Memória RAM
    
    UI->>Protocol: poke(address=0x0104, size=2, value=0x0004)
    Note over Protocol: Valida parâmetros
    
    Protocol->>Protocol: Converte valor para bytes
    Note right of Protocol: 0x0004 → [0x04, 0x00]<br/>(little-endian)
    
    Protocol->>Protocol: Constrói pacote
    Note right of Protocol: [0xCA][0xFE][0xF2]<br/>[0x04][0x01][0x02]<br/>[0x04][0x00]
    
    Protocol->>Serial: write(8 bytes)
    Serial->>Arduino: Transmite bytes
    
    loop Para cada byte 1-6
        Arduino->>Arduino: Processa cabeçalho
    end
    
    Note over Arduino: Estado: WAIT_VALUE<br/>Aguarda 2 bytes de dados
    
    loop Para bytes 7-8
        Arduino->>Arduino: Armazena no buffer<br/>destraValueBuffer[]
    end
    
    Note over Arduino: Estado: PROCESS_REQUEST<br/>Comando: POKE
    
    Arduino->>Arduino: Valida endereço
    Arduino->>RAM: Escreve 2 bytes em 0x0104
    RAM-->>Arduino: Confirmação
    
    Arduino->>RAM: Lê de volta para verificação
    RAM-->>Arduino: Retorna [0x04, 0x00]
    
    Arduino->>Arduino: Constrói resposta
    Note right of Arduino: [0xCA][0xFE][0xF2]<br/>[0x00][0x04][0x00]<br/>(echo dos dados)
    
    Arduino->>Serial: write(6 bytes)
    Serial->>Protocol: read(6 bytes)
    
    Protocol->>Protocol: Valida resposta
    Protocol->>Protocol: Verifica echo
    Note over Protocol: Dados enviados == Dados recebidos ✓
    
    Protocol-->>UI: Retorna True (sucesso)
    UI->>UI: Atualiza status
```

### Caso de Erro - Tamanho Inválido

```mermaid
sequenceDiagram
    autonumber
    participant UI as Interface (Python)
    participant Protocol as DestraProtocol
    participant Serial as Serial Port
    participant Arduino as Arduino
    
    UI->>Protocol: poke(address=0x0104, size=10, value=data)
    Note over Protocol: size > 8 (máximo)
    
    Protocol->>Protocol: Constrói pacote
    Protocol->>Serial: write(16 bytes)
    Serial->>Arduino: Transmite bytes
    
    Arduino->>Arduino: Processa cabeçalho
    Note over Arduino: Estado: WAIT_SIZE<br/>Recebe size=10
    
    Arduino->>Arduino: Valida tamanho
    Note over Arduino: 10 > 8 ❌<br/>SIZE_ERROR
    
    Arduino->>Serial: Envia erro
    Note right of Arduino: [0xCA][0xFE][0xF2]<br/>[0x02] (SIZE_ERROR)
    
    Serial->>Protocol: read(4 bytes)
    Protocol->>Protocol: Detecta erro de tamanho
    
    Protocol-->>UI: Retorna False
    UI->>UI: Exibe erro de tamanho
```

## Cenário de Auto PEEK Contínuo

```mermaid
sequenceDiagram
    autonumber
    participant UI as Interface (Python)
    participant Timer as Timer (Qt)
    participant Protocol as DestraProtocol
    participant Serial as Serial Port
    participant Arduino as Arduino
    
    UI->>Timer: Inicia Auto PEEK (10 Hz)
    
    loop A cada 100ms
        Timer->>UI: Timeout signal
        UI->>Protocol: peek(address, size)
        Protocol->>Serial: write(6 bytes)
        Serial->>Arduino: Transmite comando
        Arduino->>Arduino: Processa PEEK
        Arduino->>Serial: Envia resposta
        Serial->>Protocol: read(response)
        Protocol-->>UI: Retorna valor
        UI->>UI: Atualiza display
        
        Note over UI: Verifica se Auto PEEK<br/>ainda está ativo
        
        alt Auto PEEK desativado
            UI->>Timer: Para timer
            Note over Timer: Fim do loop
        end
    end
```

## Fluxo de Inicialização e Conexão

```mermaid
sequenceDiagram
    autonumber
    participant UI as Interface (Python)
    participant Protocol as DestraProtocol
    participant PySerial as PySerial
    participant OS as Sistema Operacional
    participant Arduino as Arduino
    
    UI->>Protocol: auto_detect_arduino()
    Protocol->>PySerial: list_ports.comports()
    PySerial->>OS: Enumera portas seriais
    OS-->>PySerial: Lista de portas
    PySerial-->>Protocol: Portas disponíveis
    
    Protocol->>Protocol: Filtra por Arduino
    Note over Protocol: Busca por:<br/>"arduino", "ch340",<br/>"ft232", "cp210"
    
    alt Arduino encontrado
        Protocol-->>UI: Retorna porta (ex: COM3)
        UI->>Protocol: connect(port="COM3")
        Protocol->>PySerial: Serial(port, 115200, 8N1)
        PySerial->>OS: Abre porta serial
        
        Note over Arduino: Reset automático<br/>na conexão USB
        
        Arduino->>Arduino: setup() → destraSetup()
        Arduino->>Serial: "Destra está pronto..."
        
        Protocol->>Protocol: sleep(2s)
        Note over Protocol: Aguarda Arduino<br/>estabilizar
        
        Protocol->>PySerial: in_waiting > 0?
        PySerial->>Serial: readline()
        Serial-->>Protocol: Mensagem inicial
        
        Protocol-->>UI: Conexão bem-sucedida
        UI->>UI: Habilita controles
    else Nenhum Arduino
        Protocol-->>UI: Lista portas disponíveis
        UI->>UI: Solicita seleção manual
    end
```

## Fluxo de Carregamento do Dicionário de Dados

```mermaid
sequenceDiagram
    autonumber
    participant UI as Interface (Python)
    participant Dict as ElfDataDictionary
    participant Parser as DWARF Parser
    participant FS as Sistema de Arquivos
    
    UI->>UI: Usuário seleciona arquivo .elf
    UI->>Dict: ElfDataDictionary(elf_path)
    
    Dict->>FS: open(elf_path, "rb")
    FS-->>Dict: File handle
    
    Dict->>Parser: ELFFile(file)
    Parser->>Parser: Valida formato ELF
    
    alt Arquivo válido com DWARF
        Parser->>Parser: get_dwarf_info()
        Parser->>Parser: iter_CUs()
        
        loop Para cada Compilation Unit
            Parser->>Parser: Analisa DIEs
            Note over Parser: Extrai:<br/>- Variáveis<br/>- Endereços<br/>- Tipos<br/>- Tamanhos
            
            Parser->>Dict: Armazena VariableInfo
        end
        
        Dict->>Dict: Processa arrays e structs
        Note over Dict: Adiciona elementos<br/>individuais de arrays<br/>e membros de structs
        
        Dict-->>UI: Retorna dicionário
        UI->>UI: Popula tabela de variáveis
        UI->>UI: Exibe total de variáveis
    else Arquivo inválido
        Parser-->>Dict: Erro: Sem DWARF info
        Dict-->>UI: Exceção
        UI->>UI: Exibe mensagem de erro
    end
```

## Interação Completa do Usuário

```mermaid
sequenceDiagram
    autonumber
    participant User as Usuário
    participant UI as Interface Gráfica
    participant Protocol as Protocolo
    participant Arduino as Arduino
    participant Dict as Dicionário ELF
    
    User->>UI: Inicia aplicação
    UI->>UI: Inicializa interface
    
    User->>UI: Clica "Conectar"
    UI->>Protocol: Auto-detecta Arduino
    Protocol-->>UI: Porta encontrada
    UI->>Protocol: Conecta
    Protocol-->>UI: Conectado
    
    User->>UI: Seleciona arquivo .elf
    UI->>Dict: Carrega dicionário
    Dict-->>UI: Variáveis carregadas
    
    User->>UI: Duplo clique em variável
    UI->>UI: Adiciona à lista de monitoramento
    
    User->>UI: Clica botão PEEK
    UI->>Protocol: peek(address, size)
    Protocol->>Arduino: Envia comando
    Arduino-->>Protocol: Retorna dados
    Protocol-->>UI: Valor decodificado
    UI->>UI: Atualiza célula
    
    User->>UI: Duplo clique célula POKE
    UI->>UI: Habilita edição
    User->>UI: Digita novo valor
    User->>UI: Clica botão POKE
    UI->>Protocol: poke(address, size, value)
    Protocol->>Arduino: Envia comando
    Arduino-->>Protocol: Confirmação
    Protocol-->>UI: Sucesso
    UI->>UI: Atualiza status
    
    User->>UI: Ativa Auto PEEK
    UI->>UI: Inicia timer
    
    loop Monitoramento contínuo
        UI->>Protocol: peek automático
        Protocol->>Arduino: Comando
        Arduino-->>Protocol: Dados
        Protocol-->>UI: Valores
        UI->>UI: Atualiza display
    end
    
    User->>UI: Desativa Auto PEEK
    UI->>UI: Para timer
    
    User->>UI: Clica "Desconectar"
    UI->>Protocol: disconnect()
    Protocol->>Protocol: Fecha serial
    UI->>UI: Desabilita controles
```

## Tratamento de Erros e Recuperação

```mermaid
sequenceDiagram
    autonumber
    participant UI as Interface
    participant Protocol as Protocolo
    participant Serial as Serial
    participant Arduino as Arduino
    
    Note over UI,Arduino: Cenário: Perda de sincronização
    
    UI->>Protocol: peek(address, size)
    Protocol->>Serial: Envia comando
    Serial->>Arduino: Bytes corrompidos
    
    Arduino->>Arduino: Estado incorreto
    Note over Arduino: Aguarda 0xCA para<br/>resincronizar
    
    Protocol->>Protocol: Timeout (2s)
    Protocol->>Serial: flush buffers
    
    Note over Protocol: Tenta resincronizar
    
    Protocol->>Serial: Envia sequência de 0xCA
    Serial->>Arduino: [0xCA][0xCA][0xCA]...
    
    Arduino->>Arduino: Detecta 0xCA
    Note over Arduino: Volta para<br/>WAIT_START_HIGH
    
    Arduino->>Arduino: Aguarda 0xFE
    Note over Arduino: Pronto para<br/>novo comando
    
    Protocol->>Serial: Reenvia comando
    Serial->>Arduino: Comando válido
    Arduino->>Serial: Resposta
    Serial->>Protocol: Dados
    Protocol-->>UI: Operação recuperada
```

## Temporização e Performance

```mermaid
sequenceDiagram
    participant UI as Interface
    participant Protocol as Protocolo
    participant Arduino as Arduino
    
    Note over UI,Arduino: Análise de temporização
    
    UI->>Protocol: peek(0x0104, 2)
    activate Protocol
    Note right of Protocol: t0: Início
    
    Protocol->>Arduino: 6 bytes @ 115200 bps
    Note right of Protocol: ~520μs transmissão
    
    activate Arduino
    Arduino->>Arduino: Processa comando
    Note right of Arduino: ~100-200μs processamento
    
    Arduino->>Arduino: Lê memória
    Note right of Arduino: ~10μs acesso RAM
    
    Arduino->>Protocol: 6 bytes resposta
    Note right of Arduino: ~520μs transmissão
    deactivate Arduino
    
    Protocol->>Protocol: Processa resposta
    Note right of Protocol: ~50μs decodificação
    
    Protocol-->>UI: Retorna valor
    deactivate Protocol
    Note right of Protocol: t1: Fim
    
    Note over UI,Arduino: Tempo total: ~1.2-1.3ms por operação
    Note over UI,Arduino: Throughput máximo teórico: ~770 ops/s
    Note over UI,Arduino: Throughput prático: ~500-600 ops/s
```

## Notas de Implementação

### Considerações de Design

1. **Protocolo Assíncrono**: A máquina de estados no Arduino processa bytes conforme chegam, sem bloqueio
2. **Palavra Mágica**: 0xCAFE permite resincronização rápida após erros
3. **Echo em POKE**: Verificação adicional de integridade dos dados escritos
4. **Timeout**: 2 segundos no lado Python para detectar falhas de comunicação

### Limitações Conhecidas

- **Bandwidth**: Limitado a 115200 bps (aproximadamente 11.5 KB/s)
- **Latência**: ~1-2ms por operação peek/poke
- **Buffer**: Máximo de 8 bytes por operação
- **Endereçamento**: 16 bits (0x0000-0xFFFF)
- **Concorrência**: Operações não são thread-safe

### Visualização dos Diagramas

Este documento utiliza sintaxe Mermaid para os diagramas de sequência. Para visualização:

1. **GitHub/GitLab**: Renderização automática no navegador
2. **VS Code**: Instalar extensão "Mermaid Preview" ou "Markdown Preview Mermaid Support"
3. **Online**: [Mermaid Live Editor](https://mermaid.live)
4. **Exportação**: Os diagramas podem ser exportados como PNG/SVG para documentação

## Referências

- Protocolo DESTRA: `arduino/sample/destra_protocol.ino`
- Implementação Python: `src/destra.py`
- Interface Gráfica: `src/destra_ui.py`
- Parser ELF/DWARF: `src/data_dictionary.py`

---

*Documento gerado para o projeto DESTRA - DEpurador de Sistemas em Tempo ReAl*  
*EESC - USP (2024)*
