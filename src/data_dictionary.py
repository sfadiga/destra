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
    ELF Data Dictionary Parser para Arduino Uno.
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
from enum import Enum
from dataclasses import dataclass
from pathlib import Path
from typing import Dict, List, Optional, Tuple, Union

from elftools.dwarf.die import DIE
from elftools.elf.elffile import ELFFile


@dataclass
class VariableInfo:
    """Information about a variable extracted from the ELF file."""

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

class DecodedTypes():

    @staticmethod
    def decode_type(vartype: str) -> tuple[str, int] | None:
        LookupTable = {'uint8': ('I', 1),
                   'uint16': ('I', 2), 
                   'uint32': ('I', 4), 
                   'int8': ('i', 1), 
                   'int16': ('i', 2), 
                   'int32': ('i', 4), 
                   'float': ('f', 4), 
                   'double': ('d', 8)
                   }
        return LookupTable.get(vartype, None)


class ElfDataDictionary:
    """
    A simplified ELF parser for extracting variable information.

    This class provides methods to list and query variables from an ELF file
    with DWARF debug information, optimized for peek/poke operations.
    """

    # Type mapping for basic C types to simplified categories
    TYPE_MAPPING = {
        ("unsigned char", 1): ("uint8", False),
        ("uint8_t", 1): ("uint8", False),
        ("char", 1): ("int8", True),
        ("signed char", 1): ("int8", True),
        ("unsigned short", 2): ("uint16", False),
        ("uint16_t", 2): ("uint16", False),
        ("short", 2): ("int16", True),
        ("int", 2): ("int16", True),  # Arduino Uno int is 16-bit
        ("unsigned int", 2): ("uint16", False),
        ("unsigned long", 4): ("uint32", False),
        ("uint32_t", 4): ("uint32", False),
        ("long", 4): ("int32", True),
        ("long int", 4): ("int32", True),
        ("float", 4): ("float", True),
        ("double", 4): ("float", True),  # Arduino Uno double is same as float
    }

    def __init__(self, elf_path: Union[str, Path]):
        """
        Initialize the ELF data dictionary parser.

        Args:
            elf_path: Path to the ELF file

        Raises:
            FileNotFoundError: If the ELF file doesn't exist
            ValueError: If the file is not a valid ELF file or lacks debug info
        """
        self.elf_path = Path(elf_path)
        if not self.elf_path.exists():
            raise FileNotFoundError(f"ELF file not found: {self.elf_path}")

        self._variables: Dict[str, VariableInfo] = {}
        self._parse_elf_file()

    def _parse_elf_file(self) -> None:
        """Parse the ELF file and extract variable information."""
        with open(self.elf_path, "rb") as f:
            try:
                elffile = ELFFile(f)
            except Exception as e:
                raise ValueError(f"Invalid ELF file: {e}")

            if not elffile.has_dwarf_info():
                raise ValueError("ELF file lacks DWARF debug information")

            dwarf_info = elffile.get_dwarf_info()

            # Parse all compilation units
            for cu in dwarf_info.iter_CUs():
                self._parse_compilation_unit(cu)

    def _parse_compilation_unit(self, cu) -> None:
        """Parse a single compilation unit for variables."""
        # Build a cache of DIE offsets to parsed type information
        type_cache = {}

        # First pass: parse all type definitions
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

        # Second pass: parse variables
        for die in cu.iter_DIEs():
            if (
                die.tag == "DW_TAG_variable"
                and "DW_AT_declaration" not in die.attributes
            ):
                self._parse_variable(die, cu, type_cache)

    def _parse_type(self, die: DIE, cu, type_cache: dict) -> Optional[dict]:
        """Parse type information from a DIE."""
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
                    # Unknown base type, store raw info
                    type_info = {
                        "base_type": name_str,
                        "size": size_val,
                        "is_signed": "unsigned" not in name_str.lower(),
                        "is_pointer": False,
                        "is_array": False,
                        "is_struct": False,
                    }

        elif die.tag == "DW_TAG_typedef":
            # Follow the typedef to the actual type
            type_attr = die.attributes.get("DW_AT_type")
            if type_attr:
                ref_offset = self._get_reference_offset(type_attr, cu)
                if ref_offset in type_cache:
                    type_info = type_cache[ref_offset].copy()
                else:
                    # Try to find the referenced DIE
                    ref_die = self._get_die_at_offset(cu, ref_offset)
                    if ref_die:
                        type_info = self._parse_type(ref_die, cu, type_cache) or {}

        elif die.tag == "DW_TAG_pointer_type":
            type_info = {
                "base_type": "uint16",  # Pointers are 16-bit on Arduino Uno
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

                # Get array dimensions
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

            if size:  # Only process complete struct definitions
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

                # Parse struct members
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
            # These are type qualifiers, follow to the actual type
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
        """Parse a struct member."""
        name = die.attributes.get("DW_AT_name")
        type_attr = die.attributes.get("DW_AT_type")
        location = die.attributes.get("DW_AT_data_member_location")

        if name and type_attr:
            member_name = name.value.decode("utf-8")
            ref_offset = self._get_reference_offset(type_attr, cu)
            member_type = type_cache.get(ref_offset, {})

            offset = 0
            if location:
                # Extract offset from location
                if isinstance(location.value, list) and len(location.value) > 1:
                    # DW_OP_plus_uconst format
                    offset = location.value[1]
                elif isinstance(location.value, int):
                    offset = location.value

            return {"name": member_name, "offset": offset, "type_info": member_type}

        return None

    def _parse_variable(self, die: DIE, cu, type_cache: dict) -> None:
        """Parse a variable DIE and add it to the dictionary."""
        name_attr = die.attributes.get("DW_AT_name")
        type_attr = die.attributes.get("DW_AT_type")
        location_attr = die.attributes.get("DW_AT_location")

        # Must have at least name and type
        if not (name_attr and type_attr):
            return

        var_name = name_attr.value.decode("utf-8")

        # Get address from location if available
        address = 0
        if location_attr:
            address = self._extract_address(location_attr.value)
            if address is None:
                # If we can't extract address, try to use a default or skip
                # Some variables might be optimized out or in registers
                print(f"Warning: Could not extract address for variable '{var_name}'")
                # For now, we'll still add it with address 0
                address = 0
        else:
            # Variable without location - might be external, const, or optimized
            # Check if it's external
            if "DW_AT_external" in die.attributes:
                print(f"Info: Variable '{var_name}' is external (global)")
                # External variables should have addresses, but might need linking
                address = 0  # Will be resolved at link time
            else:
                print(f"Info: Variable '{var_name}' has no location (might be optimized out)")
                # Still add it with address 0 for completeness
                address = 0

        # Get type information
        ref_offset = self._get_reference_offset(type_attr, cu)
        type_info = type_cache.get(ref_offset, {})

        if not type_info:
            return

        # Create base variable info
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

        # If it's an array, add individual element entries
        if type_info.get("is_array") and type_info.get("array_dimensions"):
            self._add_array_elements(var_name, var_info, type_info)

        # If it's a struct, add member entries
        if type_info.get("is_struct") and "members" in type_info:
            self._add_struct_members(var_name, var_info, type_info)

    def _add_array_elements(
        self, base_name: str, base_info: VariableInfo, type_info: dict
    ) -> None:
        """Add individual array element entries."""
        dimensions = type_info["array_dimensions"]
        element_size = type_info["size"] // (dimensions[0] if dimensions else 1)

        # For now, just handle 1D arrays
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
        """Add struct member entries."""
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
        """Get the absolute offset for a reference attribute."""
        offset = attr.value
        if attr.form == "DW_FORM_ref4":
            # CU-relative offset
            offset += cu.cu_offset
        return offset

    def _get_die_at_offset(self, cu, offset: int) -> Optional[DIE]:
        """Get a DIE at a specific offset within a CU."""
        try:
            return cu._get_cached_DIE(offset)
        except:
            return None

    def _extract_address(self, location_value) -> Optional[int]:
        """Extract address from DWARF location expression."""
        if isinstance(location_value, list):
            if len(location_value) == 0:
                return None
            
            # Check for DW_OP_addr (0x03) - direct address
            if location_value[0] == 0x03 and len(location_value) >= 3:
                # Address follows the opcode (16-bit for AVR)
                return int.from_bytes(bytes(location_value[1:3]), "little")
            
            # Check for other common location expressions
            # DW_OP_fbreg - frame base relative (local variables)
            if location_value[0] == 0x91:
                # This is a stack-relative variable, we can't get absolute address
                return None
            
            # Try to extract from the last 2 bytes (legacy behavior)
            if len(location_value) >= 2:
                # Some compilers put the address directly without opcode
                return int.from_bytes(bytes(location_value[-2:]), "little")
        
        elif isinstance(location_value, int):
            # Direct address value
            return location_value
        
        return None

    # Public API methods

    def list_variables(self, pattern: Optional[str] = None) -> List[str]:
        """
        List all variable names, optionally filtered by pattern.

        Args:
            pattern: Optional glob pattern to filter variable names (e.g., "dig*pin*pgm")

        Returns:
            List of variable names matching the pattern
        """
        names = list(self._variables.keys())

        if pattern:
            # Convert glob pattern to case-insensitive matching
            import fnmatch

            pattern_lower = pattern.lower()
            names = [
                name for name in names if fnmatch.fnmatch(name.lower(), pattern_lower)
            ]

        return sorted(names)

    def get_variable_info(self, name: str) -> Optional[Tuple[int, int, str]]:
        """
        Get variable information by name.

        Args:
            name: Variable name (can include array indices or struct members)

        Returns:
            Tuple of (address, size, type) or None if not found
        """
        var_info = self._variables.get(name)
        if var_info:
            return (var_info.address, var_info.size, var_info.base_type)
        return None

    def get_detailed_variable_info(self, name: str) -> Optional[VariableInfo]:
        """
        Get detailed variable information by name.

        Args:
            name: Variable name

        Returns:
            VariableInfo object or None if not found
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
        Search variables with multiple filters.

        Args:
            pattern: Glob pattern for name matching
            min_size: Minimum variable size in bytes
            max_size: Maximum variable size in bytes
            var_type: Filter by type (e.g., 'uint8', 'float', 'struct')

        Returns:
            List of VariableInfo objects matching all criteria
        """
        results = []

        # First filter by name pattern
        matching_names = self.list_variables(pattern)

        for name in matching_names:
            var_info = self._variables[name]

            # Apply size filters
            if min_size is not None and var_info.size < min_size:
                continue
            if max_size is not None and var_info.size > max_size:
                continue

            # Apply type filter
            if var_type is not None and var_info.base_type != var_type:
                continue

            results.append(var_info)

        return results

    def get_all_variables(self) -> Dict[str, VariableInfo]:
        """Get all variables as a dictionary."""
        return self._variables.copy()


def main():
    """Example usage of the ELF data dictionary."""
    import sys
    from pathlib import Path

    if len(sys.argv) < 2:
        print("Usage: python elf_data_dictionary.py <elf_file>")
        sys.exit(1)

    elf_path = Path(sys.argv[1])

    try:
        # Create the data dictionary
        data_dict = ElfDataDictionary(elf_path)

        # Example 1: List all variables
        print("Total variables found:", len(data_dict.get_all_variables()))
        print()

        # Example 2: Search for digital pin related variables
        print("Digital pin variables:")
        for name in data_dict.list_variables("*digital*pin*"):
            info = data_dict.get_variable_info(name)
            if info:
                addr, size, var_type = info
                print(f"  {name}: addr=0x{addr:04X}, size={size}, type={var_type}")
        print()

        # Example 3: Search for timer variables
        print("Timer variables:")
        for var in data_dict.search_variables("timer*"):
            print(
                f"  {var.name}: addr=0x{var.address:04X}, size={var.size}, type={var.base_type}"
            )
        print()

        # Example 4: Find all float variables
        print("Float variables:")
        for var in data_dict.search_variables("*", var_type="float"):
            print(f"  {var.name}: addr=0x{var.address:04X}")

    except FileNotFoundError as e:
        print(f"Error: {e}")
    except ValueError as e:
        print(f"Error: {e}")


if __name__ == "__main__":
    main()
