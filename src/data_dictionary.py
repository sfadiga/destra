#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Arquivo: data_dictionary.py
Autor: Sandro Fadiga
Instituição: EESC - USP (Escola de Engenharia de São Carlos)
Projeto: DESTRA - DEpurador de Sistemas em Tempo ReAl
Data de Criação: 09/01/2025
Versão: 1.0

Descrição:
    Analisador de Dicionário de Dados ELF para Arduino Uno.
    Este módulo fornece uma interface simplificada para extrair informações
    de variáveis de arquivos ELF com informações de debug DWARF, especificamente
    projetado para implementar funcionalidade peek/poke no Arduino Uno.

Funcionalidades:
    - Análise de arquivos ELF com informações DWARF
    - Extração de endereços e tipos de variáveis
    - Suporte para arrays, structs e tipos básicos
    - Interface simplificada para operações peek/poke
    - Busca e filtragem de variáveis por padrões

Dependências:
    - pyelftools: Para análise de arquivos ELF e DWARF

Licença: MIT
"""

from __future__ import annotations
from dataclasses import dataclass
from pathlib import Path
from typing import Dict, List, Optional, Tuple, Union

from elftools.dwarf.die import DIE
from elftools.elf.elffile import ELFFile

from logger_config import DestraLogger

# Configurar logger para este módulo
logger_manager = DestraLogger()
logger = logger_manager.logger.getChild("DataDictionary")


@dataclass
class VariableInfo:
    """Informações sobre uma variável extraída do arquivo ELF."""

    name: str
    address: int
    size: int
    base_type: str  # 'uint8', 'uint16', 'uint32', 'int8', 'int16', 'int32', 'float', 'double', 'struct', 'array'
    is_signed: bool
    is_pointer: bool
    array_dimensions: Optional[List[int]] = None
    struct_name: Optional[str] = None

    def __hash__(self) -> int:
        return hash(self.name)


class DecodedTypes:

    @staticmethod
    def decode_type(vartype: str) -> tuple[str, int] | None:
        LookupTable = {
            "bytes": ("<B", -1),
            "uint8": ("<B", 1),
            "int8": ("<b", 1),
            "uint16": ("<H", 2),
            "int16": ("<h", 2),
            "uint32": ("<I", 4),
            "int32": ("<i", 4),
            "long unsigned int": ("<I", 4),
            "long": ("<i", 4),
            "long signed int": ("<i", 4),
            "float": ("f", 4),
            "double": ("d", 8),
        }
        return LookupTable.get(vartype, None)

class ElfDataDictionary:
    """
    Um analisador ELF simplificado para extrair informações de variáveis.

    Esta classe fornece métodos para listar e consultar variáveis de um arquivo ELF
    com informações de debug DWARF, otimizado para operações peek/poke.
    """

    # Mapeamento de tipos C básicos para categorias simplificadas
    TYPE_MAPPING = {
        ("unsigned char", 1): ("uint8", False),
        ("uint8_t", 1): ("uint8", False),
        ("char", 1): ("int8", True),
        ("signed char", 1): ("int8", True),
        ("unsigned short", 2): ("uint16", False),
        ("uint16_t", 2): ("uint16", False),
        ("short", 2): ("int16", True),
        ("int", 2): ("int16", True),  # int do Arduino Uno é 16-bit
        ("unsigned int", 2): ("uint16", False),
        ("unsigned long", 4): ("uint32", False),
        ("uint32_t", 4): ("uint32", False),
        ("long", 4): ("int32", True),
        ("long int", 4): ("int32", True),
        ("float", 4): ("float", True),
        ("double", 4): ("float", True),  # double do Arduino Uno é igual a float
    }

    def __init__(self, elf_path: Union[str, Path]):
        """
        Inicializar o analisador de dicionário de dados ELF.

        Args:
            elf_path: Caminho para o arquivo ELF

        Raises:
            FileNotFoundError: Se o arquivo ELF não existir
            ValueError: Se o arquivo não for um ELF válido ou não tiver informações de debug
        """
        self.elf_path = Path(elf_path)
        if not self.elf_path.exists():
            raise FileNotFoundError(f"Arquivo ELF não encontrado: {self.elf_path}")

        self._variables: Dict[str, VariableInfo] = {}
        self._parse_elf_file()

    def _parse_elf_file(self) -> None:
        """Analisar o arquivo ELF e extrair informações de variáveis."""
        with open(self.elf_path, "rb") as f:
            try:
                elffile = ELFFile(f)
            except Exception as e:
                raise ValueError(f"Arquivo ELF inválido: {e}")

            if not elffile.has_dwarf_info():
                raise ValueError("Arquivo ELF não possui informações de debug DWARF")

            dwarf_info = elffile.get_dwarf_info()

            # Analisar todas as unidades de compilação
            for cu in dwarf_info.iter_CUs():
                self._parse_compilation_unit(cu)

    def _parse_compilation_unit(self, cu) -> None:
        """Analisar uma única unidade de compilação para variáveis."""
        # Construir um cache de offsets DIE para informações de tipo analisadas
        type_cache = {}

        # Primeira passada: analisar todas as definições de tipo
        for die in cu.iter_DIEs():
            if die.tag in [
                "DW_TAG_base_type",
                "DW_TAG_typedef",
                "DW_TAG_structure_type",
                "DW_TAG_array_type",
                "DW_TAG_pointer_type",
                "DW_TAG_const_type",
                "DW_TAG_volatile_type",
            ]:
                type_info = self._parse_type(die, cu, type_cache)
                if type_info:
                    type_cache[die.offset] = type_info

        # Segunda passada: analisar variáveis
        for die in cu.iter_DIEs():
            if (
                die.tag == "DW_TAG_variable"
                and "DW_AT_declaration" not in die.attributes
            ):
                self._parse_variable(die, cu, type_cache)

    def _parse_type(self, die: DIE, cu, type_cache: dict) -> Optional[dict]:
        """Analisar informações de tipo de um DIE."""
        type_info = {}

        if die.tag == "DW_TAG_base_type":
            name = die.attributes.get("DW_AT_name")
            size = die.attributes.get("DW_AT_byte_size")
            if name and size:
                name_str = name.value.decode("utf-8")
                size_val = size.value
                type_key = (name_str, size_val)

                if type_key in self.TYPE_MAPPING:
                    base_type, is_signed = self.TYPE_MAPPING[type_key]
                    type_info = {
                        "base_type": base_type,
                        "size": size_val,
                        "is_signed": is_signed,
                        "is_pointer": False,
                        "is_array": False,
                        "is_struct": False,
                    }
                else:
                    # Tipo base desconhecido, armazenar informação bruta
                    type_info = {
                        "base_type": name_str,
                        "size": size_val,
                        "is_signed": "unsigned" not in name_str.lower(),
                        "is_pointer": False,
                        "is_array": False,
                        "is_struct": False,
                    }

        elif die.tag == "DW_TAG_typedef":
            # Seguir o typedef até o tipo real
            type_attr = die.attributes.get("DW_AT_type")
            if type_attr:
                ref_offset = self._get_reference_offset(type_attr, cu)
                if ref_offset in type_cache:
                    type_info = type_cache[ref_offset].copy()
                else:
                    # Tentar encontrar o DIE referenciado
                    ref_die = self._get_die_at_offset(cu, ref_offset)
                    if ref_die:
                        type_info = self._parse_type(ref_die, cu, type_cache) or {}

        elif die.tag == "DW_TAG_pointer_type":
            type_info = {
                "base_type": "uint16",  # Ponteiros são 16-bit no Arduino Uno
                "size": 2,
                "is_signed": False,
                "is_pointer": True,
                "is_array": False,
                "is_struct": False,
            }

        elif die.tag == "DW_TAG_array_type":
            type_attr = die.attributes.get("DW_AT_type")
            if type_attr:
                ref_offset = self._get_reference_offset(type_attr, cu)
                element_type = type_cache.get(ref_offset, {})

                # Obter dimensões do array
                dimensions = []
                for child in die.iter_children():
                    if child.tag == "DW_TAG_subrange_type":
                        upper_bound = child.attributes.get("DW_AT_upper_bound")
                        if upper_bound:
                            dimensions.append(upper_bound.value + 1)

                if element_type and dimensions:
                    total_size = element_type.get("size", 1)
                    for dim in dimensions:
                        total_size *= dim

                    type_info = element_type.copy()
                    type_info["is_array"] = True
                    type_info["array_dimensions"] = dimensions
                    type_info["size"] = total_size

        elif die.tag == "DW_TAG_structure_type":
            name = die.attributes.get("DW_AT_name")
            size = die.attributes.get("DW_AT_byte_size")

            if size:  # Processar apenas definições completas de struct
                struct_name = name.value.decode("utf-8") if name else "anonymous_struct"
                type_info = {
                    "base_type": "struct",
                    "size": size.value,
                    "is_signed": False,
                    "is_pointer": False,
                    "is_array": False,
                    "is_struct": True,
                    "struct_name": struct_name,
                }

                # Analisar membros da struct
                members = []
                for member_die in die.iter_children():
                    if member_die.tag == "DW_TAG_member":
                        member_info = self._parse_struct_member(
                            member_die, cu, type_cache
                        )
                        if member_info:
                            members.append(member_info)

                type_info["members"] = members

        elif die.tag in ["DW_TAG_const_type", "DW_TAG_volatile_type"]:
            # Estes são qualificadores de tipo, seguir até o tipo real
            type_attr = die.attributes.get("DW_AT_type")
            if type_attr:
                ref_offset = self._get_reference_offset(type_attr, cu)
                if ref_offset in type_cache:
                    type_info = type_cache[ref_offset].copy()
                else:
                    ref_die = self._get_die_at_offset(cu, ref_offset)
                    if ref_die:
                        type_info = self._parse_type(ref_die, cu, type_cache) or {}

        return type_info

    def _parse_struct_member(self, die: DIE, cu, type_cache: dict) -> Optional[dict]:
        """Analisar um membro de struct."""
        name = die.attributes.get("DW_AT_name")
        type_attr = die.attributes.get("DW_AT_type")
        location = die.attributes.get("DW_AT_data_member_location")

        if name and type_attr:
            member_name = name.value.decode("utf-8")
            ref_offset = self._get_reference_offset(type_attr, cu)
            member_type = type_cache.get(ref_offset, {})

            offset = 0
            if location:
                # Extrair offset da localização
                if isinstance(location.value, list) and len(location.value) > 1:
                    # Formato DW_OP_plus_uconst
                    offset = location.value[1]
                elif isinstance(location.value, int):
                    offset = location.value

            return {"name": member_name, "offset": offset, "type_info": member_type}

        return None

    def _parse_variable(self, die: DIE, cu, type_cache: dict) -> None:
        """Analisar um DIE de variável e adicioná-lo ao dicionário."""
        name_attr = die.attributes.get("DW_AT_name")
        type_attr = die.attributes.get("DW_AT_type")
        location_attr = die.attributes.get("DW_AT_location")

        # Deve ter pelo menos nome e tipo
        if not (name_attr and type_attr):
            return

        var_name = name_attr.value.decode("utf-8")

        # Obter endereço da localização se disponível
        address = 0
        if location_attr:
            address = self._extract_address(location_attr.value)
            if address is None:
                # Se não conseguirmos extrair o endereço, tentar usar um padrão ou pular
                # Algumas variáveis podem estar otimizadas ou em registradores
                logger.warning(
                    f"Não foi possível extrair endereço para variável '{var_name}'"
                )
                # Por enquanto, ainda vamos adicioná-la com endereço 0
                address = 0
        else:
            # Variável sem localização - pode ser externa, const ou otimizada
            # Verificar se é externa
            if "DW_AT_external" in die.attributes:
                logger.debug(f"Variável '{var_name}' é externa (global)")
                # Variáveis externas devem ter endereços, mas podem precisar de linking
                address = 0  # Será resolvido no tempo de link
            else:
                logger.debug(
                    f"Variável '{var_name}' não tem localização (pode estar otimizada)"
                )
                # Ainda adicionar com endereço 0 para completude
                address = 0

        # Obter informações de tipo
        ref_offset = self._get_reference_offset(type_attr, cu)
        type_info = type_cache.get(ref_offset, {})

        if not type_info:
            return

        # Criar informações base da variável
        var_info = VariableInfo(
            name=var_name,
            address=address,
            size=type_info.get("size", 0),
            base_type=type_info.get("base_type", "unknown"),
            is_signed=type_info.get("is_signed", False),
            is_pointer=type_info.get("is_pointer", False),
            array_dimensions=type_info.get("array_dimensions"),
            struct_name=type_info.get("struct_name"),
        )

        self._variables[var_name] = var_info

        # Se for um array, adicionar entradas de elementos individuais
        if type_info.get("is_array") and type_info.get("array_dimensions"):
            self._add_array_elements(var_name, var_info, type_info)

        # Se for uma struct, adicionar entradas de membros
        if type_info.get("is_struct") and "members" in type_info:
            self._add_struct_members(var_name, var_info, type_info)

    def _add_array_elements(
        self, base_name: str, base_info: VariableInfo, type_info: dict
    ) -> None:
        """Adicionar entradas de elementos individuais do array."""
        dimensions = type_info["array_dimensions"]
        element_size = type_info["size"] // (dimensions[0] if dimensions else 1)

        # Por enquanto, apenas lidar com arrays 1D
        if len(dimensions) == 1:
            for i in range(dimensions[0]):
                element_name = f"{base_name}[{i}]"
                element_info = VariableInfo(
                    name=element_name,
                    address=base_info.address + (i * element_size),
                    size=element_size,
                    base_type=base_info.base_type,
                    is_signed=base_info.is_signed,
                    is_pointer=False,
                    array_dimensions=None,
                    struct_name=None,
                )
                self._variables[element_name] = element_info

    def _add_struct_members(
        self, base_name: str, base_info: VariableInfo, type_info: dict
    ) -> None:
        """Adicionar entradas de membros da struct."""
        for member in type_info.get("members", []):
            member_name = f"{base_name}.{member['name']}"
            member_type_info = member.get("type_info", {})

            member_info = VariableInfo(
                name=member_name,
                address=base_info.address + member["offset"],
                size=member_type_info.get("size", 0),
                base_type=member_type_info.get("base_type", "unknown"),
                is_signed=member_type_info.get("is_signed", False),
                is_pointer=member_type_info.get("is_pointer", False),
                array_dimensions=member_type_info.get("array_dimensions"),
                struct_name=member_type_info.get("struct_name"),
            )
            self._variables[member_name] = member_info

    def _get_reference_offset(self, attr, cu) -> int:
        """Obter o offset absoluto para um atributo de referência."""
        offset = attr.value
        if attr.form == "DW_FORM_ref4":
            # Offset relativo à CU
            offset += cu.cu_offset
        return offset

    def _get_die_at_offset(self, cu, offset: int) -> Optional[DIE]:
        """Obter um DIE em um offset específico dentro de uma CU."""
        try:
            return cu._get_cached_DIE(offset)
        except:
            return None

    def _extract_address(self, location_value) -> Optional[int]:
        """Extrair endereço de expressão de localização DWARF."""
        if isinstance(location_value, list):
            if len(location_value) == 0:
                return None

            # Verificar DW_OP_addr (0x03) - endereço direto
            if location_value[0] == 0x03 and len(location_value) >= 3:
                # Endereço segue o opcode (16-bit para AVR)
                return int.from_bytes(bytes(location_value[1:3]), "little")

            # Verificar outras expressões de localização comuns
            # DW_OP_fbreg - relativo à base do frame (variáveis locais)
            if location_value[0] == 0x91:
                # Esta é uma variável relativa à pilha, não podemos obter endereço absoluto
                return None

            # Tentar extrair dos últimos 2 bytes (comportamento legado)
            if len(location_value) >= 2:
                # Alguns compiladores colocam o endereço diretamente sem opcode
                return int.from_bytes(bytes(location_value[-2:]), "little")

        elif isinstance(location_value, int):
            # Valor de endereço direto
            return location_value

        return None

    # Métodos da API pública

    def list_variables(self, pattern: Optional[str] = None) -> List[str]:
        """
        Listar todos os nomes de variáveis, opcionalmente filtrados por padrão.

        Args:
            pattern: Padrão glob opcional para filtrar nomes de variáveis (ex: "dig*pin*pgm")

        Returns:
            Lista de nomes de variáveis correspondentes ao padrão
        """
        names = list(self._variables.keys())

        if pattern:
            # Converter padrão glob para correspondência case-insensitive
            import fnmatch

            pattern_lower = pattern.lower()
            names = [
                name for name in names if fnmatch.fnmatch(name.lower(), pattern_lower)
            ]

        return sorted(names)

    def get_variable_info(self, name: str) -> Optional[Tuple[int, int, str]]:
        """
        Obter informações de variável por nome.

        Args:
            name: Nome da variável (pode incluir índices de array ou membros de struct)

        Returns:
            Tupla de (endereço, tamanho, tipo) ou None se não encontrado
        """
        var_info = self._variables.get(name)
        if var_info:
            return (var_info.address, var_info.size, var_info.base_type)
        return None

    def get_detailed_variable_info(self, name: str) -> Optional[VariableInfo]:
        """
        Obter informações detalhadas de variável por nome.

        Args:
            name: Nome da variável

        Returns:
            Objeto VariableInfo ou None se não encontrado
        """
        return self._variables.get(name)

    def search_variables(
        self,
        pattern: str,
        min_size: Optional[int] = None,
        max_size: Optional[int] = None,
        var_type: Optional[str] = None,
    ) -> List[VariableInfo]:
        """
        Buscar variáveis com múltiplos filtros.

        Args:
            pattern: Padrão glob para correspondência de nome
            min_size: Tamanho mínimo da variável em bytes
            max_size: Tamanho máximo da variável em bytes
            var_type: Filtrar por tipo (ex: 'uint8', 'float', 'struct')

        Returns:
            Lista de objetos VariableInfo correspondentes a todos os critérios
        """
        results = []

        # Primeiro filtrar por padrão de nome
        matching_names = self.list_variables(pattern)

        for name in matching_names:
            var_info = self._variables[name]

            # Aplicar filtros de tamanho
            if min_size is not None and var_info.size < min_size:
                continue
            if max_size is not None and var_info.size > max_size:
                continue

            # Aplicar filtro de tipo
            if var_type is not None and var_info.base_type != var_type:
                continue

            results.append(var_info)

        return results

    def get_all_variables(self) -> Dict[str, VariableInfo]:
        """Obter todas as variáveis como um dicionário."""
        return self._variables.copy()


def main():
    """Exemplo de uso do dicionário de dados ELF."""
    import sys
    from pathlib import Path

    # Configurar logger para o main
    test_logger = logger_manager.logger.getChild("Test")

    if len(sys.argv) < 2:
        test_logger.error("Uso: python data_dictionary.py <arquivo_elf>")
        sys.exit(1)

    elf_path = Path(sys.argv[1])

    try:
        # Criar o dicionário de dados
        data_dict = ElfDataDictionary(elf_path)

        # Exemplo 1: Listar todas as variáveis
        test_logger.info(
            f"Total de variáveis encontradas: {len(data_dict.get_all_variables())}"
        )

        # Exemplo 2: Buscar variáveis relacionadas a pinos digitais
        test_logger.info("Variáveis de pinos digitais:")
        for name in data_dict.list_variables("*digital*pin*"):
            info = data_dict.get_variable_info(name)
            if info:
                addr, size, var_type = info
                test_logger.info(
                    f"  {name}: addr=0x{addr:04X}, size={size}, type={var_type}"
                )

        # Exemplo 3: Buscar variáveis de timer
        test_logger.info("Variáveis de timer:")
        for var in data_dict.search_variables("timer*"):
            test_logger.info(
                f"  {var.name}: addr=0x{var.address:04X}, size={var.size}, type={var.base_type}"
            )

        # Exemplo 4: Encontrar todas as variáveis float
        test_logger.info("Variáveis float:")
        for var in data_dict.search_variables("*", var_type="float"):
            test_logger.info(f"  {var.name}: addr=0x{var.address:04X}")

    except FileNotFoundError as e:
        test_logger.error(f"Erro: {e}")
    except ValueError as e:
        test_logger.error(f"Erro: {e}")


if __name__ == "__main__":
    main()
