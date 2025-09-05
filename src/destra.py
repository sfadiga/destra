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
from typing import Optional
import struct

import serial
import serial.tools.list_ports


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

    def auto_detect_arduino(self) -> tuple[list, list]:
        """Auto-detectar porta COM do Arduino"""
        print("Auto-detectando porta do Arduino...")
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
                print(f"  Arduino potencial encontrado: {port.device} - {port.description}")

        if not arduino_ports:
            print("Nenhum Arduino detectado. Portas disponíveis:")
            for port in ports:
                other_ports.append(port)   
                print(f"  {port.device} - {port.description}")
            #raise Exception("Nenhum Arduino encontrado. Por favor, especifique a porta manualmente.")

        if len(arduino_ports) > 1:
            print(f"Múltiplos Arduinos encontrados. Usando o primeiro: {arduino_ports[0]}")

        return arduino_ports, other_ports

    def connect(self) -> bool:
        """Conectar ao Arduino"""
        try:
            print(f"\nConectando a {self.port} em {self.baudrate} baud...")

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
                print(f"Arduino diz: {startup_msg}")
                if "ECHO_TEST_READY" in startup_msg:
                    print("✓ Arduino está pronto!")
                    return True

            print("✓ Conectado com sucesso!")
            return True

        except serial.SerialException as e:
            print(f"✗ Falha ao conectar: {e}")
            return False

    def disconnect(self):
        """Desconectar do Arduino"""
        if self.ser and self.ser.is_open:
            self.ser.close()
            print("Desconectado do Arduino")

    def _magic_word_check(self) -> bool:
        if not self.ser or not self.ser.is_open:
            print("Não conectado!")
            return False
        self.ser.reset_input_buffer()
        self.ser.write(self.MAGIC_CA)
        echo = self.ser.read(1)
        print(f"magic_ca {echo=}")
        if echo == self.MAGIC_CA:
            self.ser.write(self.MAGIC_FE)
            echo = self.ser.read(1)
            print(f"magic_fe {echo=}")
            return echo == self.MAGIC_FE
        return False

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
            print("Não conectado!")
            return None

        # Validar parâmetros
        if not (0 <= address <= 0xFFFF):
            print(f"Endereço inválido: {address:#06x} (deve ser 0-0xFFFF)")
            return None
        if not (1 <= size <= 8):
            print(f"Tamanho inválido: {size} (deve ser 1-8)")
            return None

        try:
            # Enviar palavra mágica
            if not self._magic_word_check():
                print("Verificação de palavra mágica falhou!")
                return None

            # Enviar comando PEEK
            self.ser.write(self.PEEK_CMD)
            echo = self.ser.read(1)
            if echo != self.PEEK_CMD:
                print(
                    f"Incompatibilidade de eco do comando: esperado {self.PEEK_CMD.hex()}, recebido {echo.hex()}"
                )
                return None

            # Enviar endereço (byte baixo primeiro para expectativa little-endian do Arduino)
            address_bytes = address.to_bytes(2, "big")

            # Enviar byte baixo
            self.ser.write(bytes([address_bytes[1]]))
            echo = self.ser.read(1)
            if echo != bytes([address_bytes[1]]):
                print(f"Incompatibilidade de eco do byte baixo do endereço")
                return None

            # Enviar byte alto
            self.ser.write(bytes([address_bytes[0]]))
            echo = self.ser.read(1)
            if echo != bytes([address_bytes[0]]):
                print(f"Incompatibilidade de eco do byte alto do endereço")
                return None

            # Enviar tamanho
            self.ser.write(bytes([size]))
            echo = self.ser.read(1)
            if echo != bytes([size]):
                print(f"Incompatibilidade de eco do tamanho")
                return None

            # Ler cabeçalho da resposta
            response_header = self.ser.read(4)  # CA FE F1 STATUS
            if len(response_header) < 4:
                print(f"Cabeçalho de resposta incompleto: {response_header.hex()}")
                return None

            # Verificar cabeçalho da resposta
            if response_header[0:3] != b"\xca\xfe\xf1":
                print(f"Cabeçalho de resposta inválido: {response_header.hex()}")
                return None

            # Verificar status
            status = response_header[3]
            if status == self.STATUS_ADDRESS_RANGE_ERROR:
                print(f"Erro de faixa de endereço: {address:#06x}")
                return None
            elif status == self.STATUS_SIZE_ERROR:
                print(f"Erro de tamanho: {size}")
                return None
            elif status != self.STATUS_SUCCESS:
                print(f"Status desconhecido: {status:#04x}")
                return None

            # Ler os dados
            data = self.ser.read(size)
            if len(data) != size:
                print(f"Dados incompletos: esperado {size} bytes, recebido {len(data)}")
                return None

            # Sucesso! Retornar os dados
            print(f"Peek bem-sucedido: endereço={address:#06x}, tamanho={size}")
            print(f"Dados (hex): {' '.join(f'{b:02x}' for b in data)}")

            return data

        except serial.SerialTimeoutException:
            print("Timeout serial!")
            return None
        except Exception as e:
            print(f"Erro durante peek: {e}")
            return None

    def decode_peek_data(self, data: bytes, data_type: str = "hex") -> any:
        """
        Decodificar os bytes brutos do peek em vários tipos de dados.

        Args:
            data: Bytes brutos da operação peek
            data_type: Tipo para decodificar. Opções:
                - 'hex': String hexadecimal
                - 'uint8': Inteiro sem sinal de 8 bits
                - 'int8': Inteiro com sinal de 8 bits
                - 'uint16': Inteiro sem sinal de 16 bits (little-endian)
                - 'int16': Inteiro com sinal de 16 bits (little-endian)
                - 'uint32': Inteiro sem sinal de 32 bits (little-endian)
                - 'int32': Inteiro com sinal de 32 bits (little-endian)
                - 'float': Float de 32 bits (little-endian)
                - 'double': Double de 64 bits (little-endian)
                - 'string': String ASCII
                - 'bytes': Bytes brutos (sem decodificação)

        Returns:
            Valor decodificado no tipo especificado
        """
        if not data:
            return None

        try:
            if data_type == "hex":
                return " ".join(f"{b:02x}" for b in data)

            elif data_type == "uint8":
                if len(data) < 1:
                    raise ValueError("Precisa de pelo menos 1 byte para uint8")
                return data[0]

            elif data_type == "int8":
                if len(data) < 1:
                    raise ValueError("Precisa de pelo menos 1 byte para int8")
                return struct.unpack("<b", data[:1])[0]

            elif data_type == "uint16":
                if len(data) < 2:
                    raise ValueError("Precisa de pelo menos 2 bytes para uint16")
                return struct.unpack("<H", data[:2])[0]

            elif data_type == "int16":
                if len(data) < 2:
                    raise ValueError("Precisa de pelo menos 2 bytes para int16")
                return struct.unpack("<h", data[:2])[0]

            elif data_type in ("uint32", "long unsigned int"):
                if len(data) < 4:
                    raise ValueError("Precisa de pelo menos 4 bytes para uint32")
                return struct.unpack("<I", data[:4])[0]

            elif data_type in ("int32", "long", "long signed int"):
                if len(data) < 4:
                    raise ValueError("Precisa de pelo menos 4 bytes para int32")
                return struct.unpack("<i", data[:4])[0]

            elif data_type == "float":
                if len(data) < 4:
                    raise ValueError("Precisa de pelo menos 4 bytes para float")
                return struct.unpack("<f", data[:4])[0]

            elif data_type == "double":
                if len(data) < 8:
                    raise ValueError("Precisa de pelo menos 8 bytes para double")
                return struct.unpack("<d", data[:8])[0]

            elif data_type == "string":
                # Decodificar como ASCII, parar no terminador nulo se presente
                null_idx = data.find(b"\x00")
                if null_idx >= 0:
                    data = data[:null_idx]
                return data.decode("ascii", errors="replace")

            elif data_type == "bytes":
                return data

            else:
                raise ValueError(f"Tipo de dados desconhecido: {data_type}")

        except struct.error as e:
            print(f"Erro de desempacotamento de struct: {e}")
            return None
        except Exception as e:
            print(f"Erro de decodificação: {e}")
            return None

    def poke(self, address: int, size: int, value: float | int | bytes) -> bool:
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
            print("Não conectado!")
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
                print(f"Tamanho inválido {size} para valor inteiro")
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
            print(f"Tipo de valor não suportado: {type(value)}")
            return False

        # Validar parâmetros
        if not 0 <= address <= 0xFFFF:
            print(f"Endereço inválido: {address:#06x} (deve ser 0-0xFFFF)")
            return False
        if not 1 <= size <= 8:
            print(f"Tamanho inválido: {size} (deve ser 1-8)")
            return False
        if len(value_bytes) < size:
            print(f"Bytes do valor ({len(value_bytes)}) menor que o tamanho solicitado ({size})")
            return False

        try:
            # Enviar palavra mágica
            if not self._magic_word_check():
                print("Verificação de palavra mágica falhou!")
                return False

            # Enviar comando POKE
            self.ser.write(self.POKE_CMD)
            echo = self.ser.read(1)
            if echo != self.POKE_CMD:
                print(
                    f"Incompatibilidade de eco do comando: esperado {self.POKE_CMD.hex()}, recebido {echo.hex()}"
                )
                return False

            # Enviar endereço (byte baixo primeiro para expectativa little-endian do Arduino)
            address_bytes = address.to_bytes(2, "big")

            # Enviar byte baixo
            self.ser.write(bytes([address_bytes[1]]))
            echo = self.ser.read(1)
            if echo != bytes([address_bytes[1]]):
                print("Incompatibilidade de eco do byte baixo do endereço")
                return False

            # Enviar byte alto
            self.ser.write(bytes([address_bytes[0]]))
            echo = self.ser.read(1)
            if echo != bytes([address_bytes[0]]):
                print("Incompatibilidade de eco do byte alto do endereço")
                return False

            # Enviar tamanho
            self.ser.write(bytes([size]))
            echo = self.ser.read(1)
            if echo != bytes([size]):
                print("Incompatibilidade de eco do tamanho")
                return False
            # Enviar bytes do valor
            for i in range(size):
                self.ser.write(bytes([value_bytes[i]]))
                echo = self.ser.read(1)
                if echo != bytes([value_bytes[i]]):
                    print(f"Incompatibilidade de eco do byte {i} do valor")
                    return False

            # Ler cabeçalho da resposta
            response_header = self.ser.read(4)  # CA FE F2 STATUS
            if len(response_header) < 4:
                print(f"Cabeçalho de resposta incompleto: {response_header.hex()}")
                return False

            # Verificar cabeçalho da resposta
            if response_header[0:3] != b"\xca\xfe\xf2":  # Nota: F2 para POKE
                print(f"Cabeçalho de resposta inválido: {response_header.hex()}")
                return False

            # Verificar status
            status = response_header[3]
            if status == self.STATUS_ADDRESS_RANGE_ERROR:
                print(f"Erro de faixa de endereço: {address:#06x}")
                return False
            elif status == self.STATUS_SIZE_ERROR:
                print(f"Erro de tamanho: {size}")
                return False
            elif status != self.STATUS_SUCCESS:
                print(f"Status desconhecido: {status:#04x}")
                return False

            # Ler de volta os dados de verificação (Arduino envia de volta o que foi escrito)
            verify_data = self.ser.read(size)
            if len(verify_data) != size:
                print(f"Dados de verificação incompletos: esperado {size} bytes, recebido {len(verify_data)}")
                return False

            # Verificar se os dados foram escritos corretamente
            if verify_data != value_bytes[:size]:
                print("Verificação falhou!")
                print(f"  Enviado:     {' '.join(f'{b:02x}' for b in value_bytes[:size])}")
                print(f"  Lido de volta: {' '.join(f'{b:02x}' for b in verify_data)}")
                return False

            # Sucesso!
            print(f"Poke bem-sucedido: endereço={address:#06x}, tamanho={size}")
            print(f"Dados escritos: {' '.join(f'{b:02x}' for b in value_bytes[:size])}")
            return True

        except serial.SerialTimeoutException:
            print("Timeout serial!")
            return False
        except Exception as e:
            print(f"Erro durante poke: {e}")
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
