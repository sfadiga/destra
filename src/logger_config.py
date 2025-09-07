#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Arquivo: logger_config.py
Autor: Sandro Fadiga
Instituição: EESC - USP (Escola de Engenharia de São Carlos)
Projeto: DESTRA - DEpurador de Sistemas em Tempo ReAl
Data de Criação: 09/01/2025
Versão: 1.0

Descrição:
    Configuração centralizada de logging para o sistema DESTRA.
    Fornece um sistema de logging configurável com diferentes níveis
    (DEBUG, INFO, WARNING, ERROR, CRITICAL) e formatação padronizada.

Funcionalidades:
    - Configuração centralizada de logging
    - Níveis de log configuráveis dinamicamente
    - Formatação padronizada de mensagens
    - Suporte para múltiplos handlers (console e arquivo)

Licença: MIT
"""

import logging
import sys
from pathlib import Path


class DestraLogger:
    """Gerenciador centralizado de logging para o sistema DESTRA."""

    _instance = None
    _initialized = False

    def __new__(cls):
        if cls._instance is None:
            cls._instance = super().__new__(cls)
        return cls._instance

    def __init__(self):
        if not self._initialized:
            self._initialized = True
            self._setup_logging()
            self._current_level = logging.INFO

    def _setup_logging(self):
        """Configurar o sistema de logging."""
        # Criar diretório de logs se não existir
        log_dir = Path("logs")
        log_dir.mkdir(exist_ok=True)

        # Configurar o logger raiz
        self.logger = logging.getLogger("DESTRA")
        self.logger.setLevel(logging.DEBUG)  # Capturar todos os níveis

        # Fechar e remover handlers existentes para evitar memory leak
        for handler in self.logger.handlers[:]:
            handler.close()
            self.logger.removeHandler(handler)

        # Formato das mensagens
        formatter = logging.Formatter(
            "%(asctime)s - %(name)s - %(levelname)s - %(module)s:%(lineno)d - %(message)s",
            datefmt="%Y-%m-%d %H:%M:%S",
        )

        # Handler para console
        self.console_handler = logging.StreamHandler(sys.stdout)
        self.console_handler.setLevel(logging.INFO)
        self.console_handler.setFormatter(formatter)
        self.logger.addHandler(self.console_handler)

        # Handler para arquivo
        self.file_handler = logging.FileHandler(
            log_dir / "destra.log", mode="a", encoding="utf-8"
        )
        self.file_handler.setLevel(logging.DEBUG)
        self.file_handler.setFormatter(formatter)
        self.logger.addHandler(self.file_handler)

    def set_level(self, level: str):
        """
        Definir o nível de logging.

        Args:
            level: String representando o nível ('DEBUG', 'INFO', 'WARNING', 'ERROR', 'CRITICAL')
        """
        level_map = {
            "DEBUG": logging.DEBUG,
            "INFO": logging.INFO,
            "WARNING": logging.WARNING,
            "ERROR": logging.ERROR,
            "CRITICAL": logging.CRITICAL,
        }

        if level.upper() in level_map:
            new_level = level_map[level.upper()]
            self._current_level = new_level
            self.console_handler.setLevel(new_level)
            self.logger.info(f"Nível de logging alterado para: {level}")
        else:
            self.logger.warning(f"Nível de logging inválido: {level}")
