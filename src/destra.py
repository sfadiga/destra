#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Arquivo: destra.py
Autor: Sandro Fadiga
Instituição: EESC - USP (Escola de Engenharia de São Carlos)
Projeto: DESTRA - DEpurador de Sistemas em Tempo ReAl
Data de Criação: 09/01/2025
Versão: 1.0

Descrição:
    Implementação do protocolo de comunicação DESTRA para depuração em tempo real
    de sistemas embarcados Arduino. Este módulo fornece as funcionalidades de
    peek/poke para leitura e escrita de memória via comunicação serial.

Funcionalidades:
    - Auto-detecção de portas Arduino
    - Comunicação serial com protocolo customizado
    - Operações peek (leitura de memória)
    - Operações poke (escrita de memória)
    - Decodificação de tipos de dados (int, float, string, etc.)
    - Verificação de integridade com palavras mágicas

Protocolo:
    - Palavras mágicas: 0xCA 0xFE
    - Comandos: PEEK (0xF1), POKE (0xF2)
    - Suporte para endereços de 16 bits
    - Transferência de 1-8 bytes por operação

Dependências:
    - pyserial: Para comunicação serial

Licença: MIT
"""
import time
from typing import Optional, Union, List
import struct

import serial
import serial.tools.list_ports

from logger_config import DestraLogger

from data_dictionary import DecodedTypes


class DestraProtocol:
    """DEpurador de Sistemas em Tempo ReAl - Protocolo"""

    # PROTOCOLO
    # PALAVRA MÁGICA
    MAGIC_CA = bytes.fromhex("CA")
    MAGIC_FE = bytes.fromhex("FE")
    PEEK_CMD = bytes.fromhex("F1")
    POKE_CMD = bytes.fromhex("F2")

    # Códigos de status
    STATUS_SUCCESS = 0x00
    STATUS_ADDRESS_RANGE_ERROR = 0x01
    STATUS_SIZE_ERROR = 0x02

    def __init__(self, port: Optional[str] = None, baudrate: int = 115200):
        # Usar configuração serial padrão 8N1 (sem paridade)
        self.ser = None
        self.baudrate = baudrate
        self.port = port
        self.ser = None

        # Configurar logger
        logger_manager = DestraLogger()
        self.logger = logger_manager.logger.getChild("Protocol")

    def auto_detect_arduino(self) -> tuple[List, List]:
        """Auto-detectar porta COM do Arduino"""
        self.logger.info("Auto-detectando porta do Arduino...")
        ports = serial.tools.list_ports.comports()

        arduino_ports = []
        other_ports = []
        for port in ports:
            # Verificar identificadores comuns do Arduino
            if any(
                x in port.description.lower()
                for x in ["arduino", "ch340", "ft232", "cp210"]
            ):
                arduino_ports.append(port)
                self.logger.debug(
                    f"Arduino potencial encontrado: {port.device} - {port.description}"
                )

        if not arduino_ports:
            self.logger.warning("Nenhum Arduino detectado. Portas disponíveis:")
            for port in ports:
                other_ports.append(port)
                self.logger.debug(f"  {port.device} - {port.description}")

        if len(arduino_ports) > 1:
            self.logger.info(
                f"Múltiplos Arduinos encontrados. Usando o primeiro: {arduino_ports[0]}"
            )

        return arduino_ports, other_ports

    def connect(self) -> bool:
        """Conectar ao Arduino"""
        try:
            self.logger.info(f"Conectando a {self.port} em {self.baudrate} baud...")

            # Abrir conexão serial com configurações padrão 8N1
            self.ser = serial.Serial(
                port=self.port,
                baudrate=self.baudrate,
                bytesize=serial.EIGHTBITS,
                parity=serial.PARITY_NONE,
                stopbits=serial.STOPBITS_ONE,
                timeout=2.0,
                write_timeout=2.0,
            )

            # Limpar qualquer dado pendente
            self.ser.reset_input_buffer()
            self.ser.reset_output_buffer()

            # Aguardar o Arduino reiniciar (se ele reinicia na conexão serial)
            time.sleep(2)

            # Verificar mensagem de inicialização
            if self.ser.in_waiting > 0:
                startup_msg = self.ser.readline().decode("utf-8").strip()
                self.logger.debug(f"Arduino diz: {startup_msg}")
                if "ECHO_TEST_READY" in startup_msg:
                    self.logger.info("Arduino está pronto!")
                    return True

            self.logger.info("Conectado com sucesso!")
            return True

        except serial.SerialException as e:
            self.logger.error(f"Falha ao conectar: {e}")
            return False

    def disconnect(self):
        """Desconectar do Arduino"""
        if self.ser and self.ser.is_open:
            self.ser.close()
            self.logger.info("Desconectado do Arduino")

    def _common_protocol_payload(
        self, command: bytes, address: int, size: int
    ) -> bytes:
        """
        Constroi a parte comum ao pacote serial para ser enviado nos comandos
        """
        # Constroi a palavra magica, comando, endereço e tamanho, tansfere tudo num só write
        message: bytes = struct.pack(">c", self.MAGIC_CA)
        message += struct.pack(">c", self.MAGIC_FE)
        message += struct.pack(">c", command)
        addr_low = address & 0xFF  # extrai os 8 bits
        addr_high = (address >> 8) & 0xFF  # extrai os 8 bits
        message += struct.pack(">B", addr_low)
        message += struct.pack(">B", addr_high)
        message += struct.pack(">B", size)
        return message

    def _common_protocol_response(
        self, command: bytes, address: int = 0, size: int = 0
    ) -> tuple[bool, bytes | None]:
        if not self.ser:
            return False, None

        # Ler cabeçalho da resposta
        response_header = self.ser.read(4)  # CA FE F2 STATUS
        if len(response_header) < 4:
            self.logger.error(
                f"Cabeçalho de resposta incompleto: {response_header.hex()}"
            )
            return False, None

        # Verificar cabeçalho da resposta
        if response_header[0:3] != b"\xca\xfe" + command:  # Nota: F2 para POKE
            self.logger.error(
                f"Cabeçalho de resposta inválido: {response_header.hex()}"
            )
            return False, None

        # Verificar status
        status = response_header[3]
        if status == self.STATUS_ADDRESS_RANGE_ERROR:
            self.logger.error(f"Erro de faixa de endereço: {address:#06x}")
            return False, None
        if status == self.STATUS_SIZE_ERROR:
            self.logger.error(f"Erro de tamanho: {size}")
            return False, None
        if status != self.STATUS_SUCCESS:
            self.logger.error(f"Status desconhecido: {status:#04x}")
            return False, None

        # Ler os dados
        data = self.ser.read(size)
        if len(data) != size:
            self.logger.error(
                f"Dados incompletos: esperado {size} bytes, recebido {len(data)}"
            )
            return False, data

        return True, data

    def peek(self, address: int, size: int) -> Optional[bytes]:
        """
        Enviar uma requisição peek e retornar o conteúdo da memória no endereço especificado.

        Args:
            address: Endereço de memória para ler (16-bit)
            size: Número de bytes para ler (1-8)

        Returns:
            objeto bytes com o conteúdo da memória, ou None se falhou
        """
        if not self.ser or not self.ser.is_open:
            self.logger.error("Não conectado!")
            return None

        # Validar parâmetros
        if not 0 <= address <= 0xFFFF:
            self.logger.error(f"Endereço inválido: {address:#06x} (deve ser 0-0xFFFF)")
            return None

        if not 1 <= size <= 8:
            self.logger.error(f"Tamanho inválido: {size} (deve ser 1-8)")
            return None

        try:
            message: bytes = self._common_protocol_payload(self.PEEK_CMD, address, size)
            self.ser.write(message)
            status, data = self._common_protocol_response(self.PEEK_CMD, address, size)
            if status and data:
                # Sucesso! Retornar os dados
                self.logger.debug(
                    f"Peek bem-sucedido: endereço={address:#06x}, tamanho={size}"
                )
                self.logger.debug(f"Dados (hex): {' '.join(f'{b:02x}' for b in data)}")
            return data
        except serial.SerialTimeoutException:
            self.logger.error("Timeout serial!")
            return None
        except Exception as e:
            self.logger.error(f"Erro durante peek: {e}", exc_info=True)
            return None

    def decode_peek_data(
        self, data: Optional[bytes], data_type: str
    ) -> Union[float, int, bytes, str, None]:
        """
        Decodificar os bytes brutos do peek em vários tipos de dados.

        Args:
            data: Bytes brutos da operação peek
            data_type: Tipo para decodificar, disponiveis em Data Dictionary / Decode Types

        Returns:
            Valor decodificado no tipo especificado
        """
        try:
            if not data:
                raise ValueError("Dados inválidos para decodificar peek")

            decoded = DecodedTypes.decode_type(data_type)
            if not decoded:
                raise ValueError(f"Tipo de dados desconhecido: {data_type}")

            fmt, size = decoded

            if len(data) < size:
                raise ValueError(f"Precisa de pelo menos {size} byte para {data_type}")

            return struct.unpack(fmt, data[:size])[0]

        except struct.error as e:
            self.logger.error(f"Erro de desempacotamento de struct: {e}")
            return None
        except Exception as e:
            self.logger.error(f"Erro de decodificação: {e}")
            return None

    def poke(
        self, address: int, size: Optional[int], value: Union[float, int, bytes]
    ) -> bool:
        """
        Escrever dados na memória do Arduino no endereço especificado.

        Args:
            address: Endereço de memória para escrever (16-bit)
            value: Dados para escrever. Pode ser:
                - objeto bytes
                - int (será convertido baseado no tamanho)
                - float (será convertido para 4 bytes)
            size: Número de bytes para escrever (1-8). Se None, usa len(value)

        Returns:
            True se bem-sucedido, False caso contrário
        """
        if not self.ser or not self.ser.is_open:
            self.logger.error("Não conectado!")
            return False

        # Converter valor para bytes se necessário
        if isinstance(value, int):
            if size is None:
                # Determinar tamanho baseado no valor
                if -128 <= value <= 255:
                    size = 1
                elif -32768 <= value <= 65535:
                    size = 2
                else:
                    size = 4

            # Converter para bytes (little-endian para Arduino)
            if size == 1:
                value_bytes = struct.pack("<B" if value >= 0 else "<b", value)
            elif size == 2:
                value_bytes = struct.pack("<H" if value >= 0 else "<h", value)
            elif size == 4:
                value_bytes = struct.pack("<I" if value >= 0 else "<i", value)
            else:
                self.logger.error(f"Tamanho inválido {size} para valor inteiro")
                return False

        elif isinstance(value, float):
            value_bytes = struct.pack("<f", value)  # 4 bytes, little-endian
            if size is None:
                size = 4

        elif isinstance(value, bytes):
            value_bytes = value
            if size is None:
                size = len(value_bytes)
        else:
            self.logger.error(f"Tipo de valor não suportado: {type(value)}")
            return False

        # Validar parâmetros
        if not 0 <= address <= 0xFFFF:
            self.logger.error(f"Endereço inválido: {address:#06x} (deve ser 0-0xFFFF)")
            return False
        if not 1 <= size <= 8:
            self.logger.error(f"Tamanho inválido: {size} (deve ser 1-8)")
            return False
        if len(value_bytes) < size:
            self.logger.error(
                f"Bytes do valor ({len(value_bytes)}) menor que o tamanho solicitado ({size})"
            )
            return False

        try:
            message: bytes = self._common_protocol_payload(self.POKE_CMD, address, size)
            message += value_bytes
            self.ser.write(message)

            # Ler de volta os dados de verificação (Arduino envia de volta o que foi escrito)
            status, verify_data = self._common_protocol_response(
                self.POKE_CMD, address, size
            )
            if status and verify_data:
                # Verificar se os dados foram escritos corretamente
                if verify_data != value_bytes[:size]:
                    self.logger.error("Verificação falhou!")
                    self.logger.error(
                        f"  Enviado:     {' '.join(f'{b:02x}' for b in value_bytes[:size])}"
                    )
                    self.logger.error(
                        f"  Lido de volta: {' '.join(f'{b:02x}' for b in verify_data)}"
                    )
                    return False

                # Sucesso!
                self.logger.debug(
                    f"Poke bem-sucedido: endereço={address:#06x}, tamanho={size}"
                )
                self.logger.debug(
                    f"Dados escritos: {' '.join(f'{b:02x}' for b in value_bytes[:size])}"
                )

            return status

        except serial.SerialTimeoutException:
            self.logger.error("Timeout serial!")
            return False
        except Exception as e:
            self.logger.error(f"Erro durante poke: {e}")
            return False


def main():
    """Função principal para executar o teste de eco"""
    import sys

    # Verificar argumentos da linha de comando
    port = None
    if len(sys.argv) > 1:
        port = sys.argv[1]
        print(f"Usando porta especificada: {port}")

    try:
        # Criar instância de teste
        protocol = DestraProtocol(port=port)

        if not protocol.connect():
            print("\n✗ Falha ao conectar ao Arduino!")
            return

        # Permitir que o Arduino estabilize
        time.sleep(0.5)

        # Executar todos os testes
        data = protocol.peek(int(0x012F), 4)
        val = protocol.decode_peek_data(data, "uint32")
        print(f" {val=}")
    except Exception as e:
        print(f"\n✗ Erro: {e}")
        print("\nUso: python test_serial.py [PORTA_COM]")
        print("  Exemplo: python test_serial.py COM3")
        print("  Se nenhuma porta for especificada, tentará auto-detectar o Arduino")
        sys.exit(1)


if __name__ == "__main__":
    main()
