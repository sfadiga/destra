#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Arquivo: destra_ui.py
Autor: Sandro Fadiga
Instituição: EESC - USP (Escola de Engenharia de São Carlos)
Projeto: DESTRA - DEpurador de Sistemas em Tempo ReAl
Data de Criação: 09/01/2025
Versão: 1.0

Descrição:
    Interface gráfica (GUI) para o sistema DESTRA de depuração em tempo real.
    Fornece uma interface amigável para operações peek/poke em sistemas Arduino,
    com análise de arquivos ELF para extração de informações de variáveis.

Funcionalidades:
    - Interface gráfica intuitiva com PySide6/Qt
    - Seleção e conexão automática com Arduino
    - Carregamento e análise de arquivos ELF
    - Busca e filtragem de variáveis
    - Operações peek (leitura) e poke (escrita) de memória
    - Auto-peek com frequência configurável
    - Visualização em tabelas interativas
    - Suporte a drag-and-drop entre tabelas

Interface:
    - Seção de conexão: Detecção e conexão com Arduino
    - Seção de arquivo: Seleção de arquivo ELF
    - Tabela de variáveis disponíveis: Lista todas as variáveis do ELF
    - Tabela de variáveis selecionadas: Variáveis para monitoramento
    - Controles de peek/poke: Leitura e escrita de valores

Dependências:
    - PySide6: Framework Qt para interface gráfica
    - pyserial: Comunicação serial
    - data_dictionary: Parser de arquivos ELF
    - destra: Protocolo de comunicação DESTRA

Licença: MIT
"""

import sys
import time
from PySide6.QtWidgets import (
    QApplication,
    QMainWindow,
    QWidget,
    QVBoxLayout,
    QHBoxLayout,
    QComboBox,
    QSpinBox,
    QLineEdit,
    QPushButton,
    QTableWidget,
    QTableWidgetItem,
    QLabel,
    QFileDialog,
    QSplitter,
    QGroupBox,
    QMessageBox,
    QCheckBox,
)
from PySide6.QtCore import Qt, QTimer

# Importar o dicionário de dados ELF
from data_dictionary import ElfDataDictionary, VariableInfo
from destra import DestraProtocol
from logger_config import DestraLogger


class DestraGUI(QMainWindow):

    PERF_DUMP_FILE = "./tests/destra_ui_{freq}hz.log"
    ARDUINO_DUMP_FILE = "./tests/arduino_{freq}hz.log"

    def __init__(self):
        super().__init__()
        self.setWindowTitle("DEpurador de Sistemas em Tempo ReAl - DESTRA")
        self.setGeometry(100, 100, 1200, 800)
        self.setStyleSheet("font: 600 14pt")

        # Configurar logger
        self.logger_manager = DestraLogger()
        self.logger = self.logger_manager.logger.getChild("UI")

        # Armazenar o dicionário de dados ELF
        self.elf_data = None
        # Armazenar as variáveis do elf
        self.all_variables = []
        self._variable_list: list[VariableInfo] = []
        self._destra: DestraProtocol = DestraProtocol()
        # port -> port.device ,  port.description
        self._arduino_ports = []
        self._other_ports = []
        self._current_log = []

        # Criar widget central e layout principal
        central_widget = QWidget()
        self.setCentralWidget(central_widget)
        main_layout = QVBoxLayout(central_widget)

        # Criar layout de ui
        self._create_connection_section(main_layout)
        self._create_file_section(main_layout)
        self._create_tables_section(main_layout)

        main_layout.setStretch(0, 0)
        main_layout.setStretch(1, 0)
        main_layout.setStretch(2, 3)
        # main_layout.setStretch(3, 0)

        # Configurar timer para atualização periódica de portas COM
        self.auto_peek_timer = QTimer()
        self.auto_peek_timer.timeout.connect(self.peek_values)

        self.refresh_com_ports()
        self._is_connected = False

    def _text_2_num(self, val_txt: str) -> float | int | None:
        """Converter texto para formato int ou float, caso não consiga retorna None"""
        val = None
        try:
            val = int(val_txt)
            return val
        except:
            try:
                val = float(val_txt)
                return val
            except:
                return val

    def _create_connection_section(self, parent_layout):
        """Criar a seção de configurações de conexão"""
        group = QGroupBox("Configurações de Conexão")
        layout = QHBoxLayout()

        # Scaneia as portas disponíveis
        self.scan_button = QPushButton("Detectar")
        self.scan_button.setMinimumWidth(150)
        self.scan_button.clicked.connect(self.refresh_com_ports)
        layout.addWidget(self.scan_button)

        # Seleção de porta COM
        layout.addWidget(QLabel("Portas:"))
        self.com_port_combo = QComboBox()
        self.com_port_combo.setMinimumWidth(150)
        layout.addWidget(self.com_port_combo)

        # connecta com a porta selectionada
        self.connect_button = QPushButton("Connectar")
        self.connect_button.setMinimumWidth(150)
        self.connect_button.clicked.connect(self.connect_to_arduino)
        layout.addWidget(self.connect_button)

        # Taxa de amostragem
        self.auto_peek_check = QCheckBox()
        self.auto_peek_check.setText("Auto Peek")
        layout.addWidget(self.auto_peek_check)
        self.auto_peek_check.checkStateChanged.connect(self.start_stop_auto_peek)

        layout.addWidget(QLabel("Freq. (Hz):"))
        self.sample_rate_spin = QSpinBox()
        self.sample_rate_spin.setRange(1, 1000)
        self.sample_rate_spin.setValue(10)  # Padrão 10 Hz
        self.sample_rate_spin.valueChanged.connect(self.change_auto_peek_freq)
        self.sample_rate_spin.setSuffix(" Hz")
        layout.addWidget(self.sample_rate_spin)

        # Adicionar controle de nível de logging
        layout.addWidget(QLabel("Log Level:"))
        self.log_level_combo = QComboBox()
        self.log_level_combo.addItems(["DEBUG", "INFO", "WARNING", "ERROR", "CRITICAL"])
        self.log_level_combo.setCurrentText("ERROR")
        self.log_level_combo.currentTextChanged.connect(self.change_log_level)
        layout.addWidget(self.log_level_combo)

        self.dump_button = QPushButton("Baixar logs")
        self.dump_button.setMinimumWidth(150)
        self.dump_button.clicked.connect(self.dump_performance_logs)
        layout.addWidget(self.dump_button)

        layout.addStretch()
        group.setLayout(layout)
        parent_layout.addWidget(group)

    def _create_file_section(self, parent_layout):
        """Criar a seção de seleção de arquivo"""
        group = QGroupBox("Seleção de Arquivo ELF")
        layout = QHBoxLayout()

        layout.addWidget(QLabel("Arquivo ELF:"))
        self.file_path_edit = QLineEdit()
        self.file_path_edit.setReadOnly(True)
        self.file_path_edit.setPlaceholderText("Selecione um arquivo ELF...")
        layout.addWidget(self.file_path_edit)

        self.browse_button = QPushButton("Procurar...")
        self.browse_button.clicked.connect(self.browse_file)
        layout.addWidget(self.browse_button)

        group.setLayout(layout)
        parent_layout.addWidget(group)

    def _create_tables_section(self, parent_layout):
        """Criar a seção de duas tabelas com funcionalidade de busca"""
        # Criar divisor para tabelas redimensionáveis
        splitter = QSplitter(Qt.Horizontal)

        # Seção de variáveis disponíveis
        available_group = QGroupBox("Variáveis Disponíveis")
        available_layout = QVBoxLayout()

        # Adicionar caixa de busca para variáveis disponíveis
        search_layout = QHBoxLayout()
        search_layout.addWidget(QLabel("Buscar:"))
        self.search_edit = QLineEdit()
        self.search_edit.setPlaceholderText(
            "Digite o padrão do nome da variável (ex: timer*, *pin*, gyro_*)"
        )
        self.search_edit.textChanged.connect(self.filter_variables)
        search_layout.addWidget(self.search_edit)

        # Adicionar botão de limpar
        self.clear_search_button = QPushButton("Limpar")
        self.clear_search_button.clicked.connect(self.clear_search)
        search_layout.addWidget(self.clear_search_button)

        available_layout.addLayout(search_layout)

        # Tabela de variáveis disponíveis
        self.available_table = QTableWidget()
        self.available_table.setColumnCount(4)
        self.available_table.setHorizontalHeaderLabels(
            ["Nome", "Endereço", "Tipo", "Tamanho"]
        )
        self.available_table.horizontalHeader().setStretchLastSection(True)
        self.available_table.setSelectionBehavior(QTableWidget.SelectRows)
        self.available_table.setAlternatingRowColors(True)
        self.available_table.setSortingEnabled(True)

        # Habilitar arrastar da tabela disponível
        self.available_table.setDragEnabled(True)
        self.available_table.setDefaultDropAction(Qt.CopyAction)

        available_layout.addWidget(self.available_table)

        # Adicionar rótulo de status
        self.status_label = QLabel("Nenhum arquivo ELF carregado")
        available_layout.addWidget(self.status_label)

        available_group.setLayout(available_layout)

        # Tabela de variáveis selecionadas
        selected_group = QGroupBox("Variáveis Selecionadas")
        selected_layout = QVBoxLayout()

        self._create_buttons_section(selected_layout)

        self.selected_table = QTableWidget()
        self.selected_table.setColumnCount(3)
        self.selected_table.setHorizontalHeaderLabels(
            ["Nome", "Valor Peek", "Valor Poke"]
        )
        self.selected_table.horizontalHeader().setStretchLastSection(True)
        self.selected_table.setSelectionBehavior(QTableWidget.SelectRows)
        self.selected_table.setAlternatingRowColors(True)

        # Habilitar soltar na tabela selecionada
        self.selected_table.setAcceptDrops(True)
        self.selected_table.viewport().setAcceptDrops(True)
        self.selected_table.setDropIndicatorShown(True)

        selected_layout.addWidget(self.selected_table)
        selected_group.setLayout(selected_layout)

        # Adicionar ao divisor
        splitter.addWidget(available_group)
        splitter.addWidget(selected_group)
        splitter.setSizes([600, 600])  # Tamanhos iniciais

        parent_layout.addWidget(splitter)

        # Conectar duplo clique para adicionar variável
        self.available_table.itemDoubleClicked.connect(self.add_variable_to_selected)
        self.selected_table.itemDoubleClicked.connect(self.on_poke_cell_double_clicked)
        self.selected_table.itemChanged.connect(self.on_poke_cell_edited)

    def _create_buttons_section(self, parent_layout):
        """Criar a seção de botões de ação"""
        layout = QHBoxLayout()
        layout.addStretch()

        self.peek_button = QPushButton("Peek")
        self.peek_button.setMinimumWidth(150)
        self.peek_button.clicked.connect(self.peek_values)
        layout.addWidget(self.peek_button)

        self.poke_button = QPushButton("Poke")
        self.poke_button.setMinimumWidth(150)
        self.poke_button.clicked.connect(self.poke_values)
        layout.addWidget(self.poke_button)

        layout.addStretch()
        parent_layout.addLayout(layout)

    def connect_to_arduino(self):

        if self._is_connected:
            self._destra.disconnect()
            self.connect_button.setText("Conectar")
            self._is_connected = False
        else:
            com_port = self.com_port_combo.currentData()
            # TODO adicionar widget de seleção de baud
            baudrate = 115200
            try:
                self._destra.port = com_port
                self._destra.baudrate = baudrate
                self._destra.connect()
                self._is_connected = True
                self.connect_button.setText("Desconectar")
            except Exception as e:
                QMessageBox.critical(
                    self, "Erro", f"Erro ao conectar a porta {com_port}. {e}"
                )
                self.logger.error(f"Porta COM inválida: {e}")

    def start_stop_auto_peek(self, state: Qt.CheckState):
        if state == Qt.CheckState.Checked:
            interval_ms = int(1000.0 / self.sample_rate_spin.value())
            self.auto_peek_timer.start(interval_ms)
        elif state == Qt.CheckState.Unchecked:
            self.auto_peek_timer.stop()

    def change_auto_peek_freq(self, value: int):
        if self.auto_peek_check.isChecked():
            self._current_log = []
            self.auto_peek_timer.stop()
            interval_ms = int(1000.0 / value)
            self.auto_peek_timer.start(interval_ms)

    def change_log_level(self, level: str):
        """Alterar o nível de logging dinamicamente"""
        self.logger_manager.set_level(level)
        self.logger.info(f"Nível de logging alterado para: {level}")

    def on_poke_cell_edited(self, item):
        if item:
            item.setBackground(Qt.GlobalColor.transparent)

    def on_poke_cell_double_clicked(self, item):
        if item:
            column = item.column()
            row = item.row()

            if column == 2:  # Coluna "Valor Poke Permitir edição"
                pass
            else:
                # Remover a variável
                name_item = self.selected_table.item(row, 0)
                if name_item:
                    var_info = name_item.data(Qt.UserRole)
                    if var_info in self._variable_list:
                        self._variable_list.remove(var_info)
                self.selected_table.removeRow(row)

    def refresh_com_ports(self):
        """Atualizar a lista de portas COM disponíveis"""
        current_selection = self.com_port_combo.currentText()
        self.com_port_combo.clear()

        self._arduino_ports, self._other_ports = self._destra.auto_detect_arduino()

        ports = self._arduino_ports if self._arduino_ports else self._other_ports

        for port in ports:
            port_name = port.device
            port_desc = f"{port_name} - {port.description}"
            self.com_port_combo.addItem(port_desc, port_name)

        # Tentar restaurar seleção anterior
        index = self.com_port_combo.findText(current_selection)
        if index >= 0:
            self.com_port_combo.setCurrentIndex(index)

    def browse_file(self):
        """Abrir diálogo de arquivo para selecionar arquivo ELF"""
        file_path, _ = QFileDialog.getOpenFileName(
            self,
            "Selecionar Arquivo ELF",
            "C:/Users/sfadiga/Documents/Arduino/Destra/destra/arduino/sample/build/arduino.avr.uno/",
            "Arquivos ELF (*.elf);;Todos os Arquivos (*.*)",
        )

        if file_path:
            self.file_path_edit.setText(file_path)
            self.load_elf_file(file_path)

    def load_elf_file(self, file_path):
        """Carregar variáveis do arquivo ELF usando ElfDataDictionary"""
        try:
            # Criar dicionário de dados ELF
            self.elf_data = ElfDataDictionary(file_path)

            # Obter todas as variáveis
            all_vars = self.elf_data.get_all_variables()
            self.all_variables = list(all_vars.values())

            # Atualizar status
            self.status_label.setText(f"Carregadas {len(self.all_variables)} variáveis")

            # Preencher a tabela
            self.populate_variables_table(self.all_variables)

        except FileNotFoundError as e:
            QMessageBox.critical(self, "Erro", f"Arquivo não encontrado: {e}")
        except ValueError as e:
            QMessageBox.critical(self, "Erro", f"Arquivo ELF inválido: {e}")
        except Exception as e:
            QMessageBox.critical(self, "Erro", f"Falha ao carregar arquivo ELF: {e}")

    def populate_variables_table(self, variables):
        """Preencher a tabela de variáveis disponíveis"""
        self.available_table.setRowCount(0)

        for var in variables:
            row = self.available_table.rowCount()
            self.available_table.insertRow(row)

            # Nome
            name_item = QTableWidgetItem(var.name)
            name_item.setFlags(name_item.flags() & ~Qt.ItemIsEditable)
            self.available_table.setItem(row, 0, name_item)

            # Endereço
            addr_item = QTableWidgetItem(f"0x{var.address:04X}")
            addr_item.setFlags(addr_item.flags() & ~Qt.ItemIsEditable)
            self.available_table.setItem(row, 1, addr_item)

            # Tipo
            type_str = var.base_type
            if var.is_pointer:
                type_str += "*"
            if var.array_dimensions:
                type_str += f"[{']['.join(map(str, var.array_dimensions))}]"
            type_item = QTableWidgetItem(type_str)
            type_item.setFlags(type_item.flags() & ~Qt.ItemIsEditable)
            self.available_table.setItem(row, 2, type_item)

            # Tamanho
            size_item = QTableWidgetItem(str(var.size))
            size_item.setFlags(size_item.flags() & ~Qt.ItemIsEditable)
            self.available_table.setItem(row, 3, size_item)

            # Armazenar a informação da variável no item para fácil acesso
            name_item.setData(Qt.UserRole, var)

    def filter_variables(self, pattern):
        """Filtrar variáveis baseado no padrão de busca"""
        if not self.elf_data:
            return

        if not pattern:
            # Mostrar todas as variáveis
            self.populate_variables_table(self.all_variables)
            self.status_label.setText(
                f"Mostrando todas as {len(self.all_variables)} variáveis"
            )
        else:
            # Usar a funcionalidade de busca do ElfDataDictionary
            try:
                # Converter padrões simples para padrões glob
                if not any(c in pattern for c in ["*", "?", "[", "]"]):
                    # Se não há wildcards, adicione-os para correspondência parcial
                    pattern = f"*{pattern}*"

                # Obter nomes de variáveis correspondentes
                matching_names = self.elf_data.list_variables(pattern)

                # Obter a informação completa das variáveis correspondentes
                matching_vars = []
                for name in matching_names:
                    var_info = self.elf_data.get_detailed_variable_info(name)
                    if var_info:
                        matching_vars.append(var_info)

                # Atualizar tabela
                self.populate_variables_table(matching_vars)
                self.status_label.setText(
                    f"Encontradas {len(matching_vars)} variáveis correspondendo a '{pattern}'"
                )

            except Exception as e:
                self.status_label.setText(f"Erro na busca: {e}")

    def clear_search(self):
        """Limpar o campo de busca e mostrar todas as variáveis"""
        self.search_edit.clear()
        self.filter_variables("")

    def add_variable_to_selected(self, item):
        """Adicionar uma variável da tabela disponível para a selecionada"""
        row = item.row()

        # Obter informação da variável do item da primeira coluna
        name_item = self.available_table.item(row, 0)
        if not name_item:
            return

        var_info = name_item.data(Qt.UserRole)
        if not var_info:
            return

        self._variable_list.append(var_info)

        # Verificar se já está na tabela selecionada
        for i in range(self.selected_table.rowCount()):
            if self.selected_table.item(i, 0).text() == var_info.name:
                return  # Já foi adicionada

        # Adicionar à tabela selecionada
        new_row = self.selected_table.rowCount()
        self.selected_table.insertRow(new_row)

        # Coluna de nome (somente leitura)
        name_item = QTableWidgetItem(var_info.name)
        name_item.setFlags(name_item.flags() & ~Qt.ItemIsEditable)
        name_item.setData(Qt.UserRole, var_info)  # Armazenar informação da variável
        self.selected_table.setItem(new_row, 0, name_item)

        # Coluna de valor peek (somente leitura)
        peek_item = QTableWidgetItem("")
        peek_item.setFlags(peek_item.flags() & ~Qt.ItemIsEditable)
        self.selected_table.setItem(new_row, 1, peek_item)

        # Coluna de valor poke (editável)
        poke_item = QTableWidgetItem("")
        self.selected_table.setItem(new_row, 2, poke_item)

    def peek_values(self):
        """Obter valores peek para todas as variáveis selecionadas"""
        # Verificar se está conectado antes de executar peek
        if not self._is_connected:
            QMessageBox.warning(
                self, "Aviso", "Por favor, conecte-se ao Arduino primeiro!"
            )
            self.auto_peek_check.setChecked(False)
            return

        for var_info in self._variable_list:
            start = time.perf_counter()
            data = self._destra.peek(var_info.address, var_info.size)
            end = time.perf_counter()
            self.log_performance("PEEK", str(var_info.address), str(var_info.size), end - start)
            self.logger.debug(f"peek data={data}")
            val = self._destra.decode_peek_data(data, var_info.base_type)
            self.logger.debug(f"peek val={val}")
            # Verificar se já está na tabela selecionada
            for i in range(self.selected_table.rowCount()):
                if self.selected_table.item(i, 0).text() == var_info.name:
                    self.selected_table.item(i, 1).setData(
                        Qt.ItemDataRole.DisplayRole, val
                    )

    def poke_values(self):
        """Enviar valores poke para todas as variáveis selecionadas"""
        # Verificar se está conectado antes de executar poke
        if not self._is_connected:
            QMessageBox.warning(
                self, "Aviso", "Por favor, conecte-se ao Arduino primeiro!"
            )
            return

        self.logger.debug("Botão Poke clicado")
        for var_info in self._variable_list:
            for i in range(self.selected_table.rowCount()):
                if self.selected_table.item(i, 0).text() == var_info.name:
                    val_txt = self.selected_table.item(i, 2).text()
                    val = self._text_2_num(val_txt)
                    if val:
                        start = time.perf_counter()
                        state = self._destra.poke(var_info.address, var_info.size, val)
                        end = time.perf_counter()
                        self.log_performance("POKE", str(var_info.address), str(var_info.size), end - start)
                        if state:
                            self.selected_table.item(i, 2).setBackground(Qt.GlobalColor.darkGreen)
                            self.logger.info(f"Poke bem-sucedido: {var_info.name} = {val}")
                        else:
                            self.selected_table.item(i, 2).setBackground(Qt.GlobalColor.darkRed)
                            self.logger.warning(f"Poke falhou: {var_info.name}")

    def dump_performance_logs(self):
        """Solicitar ao Arduino o envio dos logs armazenados"""
        if not self._is_connected:
            QMessageBox.warning(self, "Aviso", "Por favor, conecte-se ao Arduino primeiro!")
            return
        try:
            dump = self._destra.performance()
            rate = self.sample_rate_spin.value()
            current_dump_file = self.PERF_DUMP_FILE.format(freq=rate)
            current_arduino_file = self.ARDUINO_DUMP_FILE.format(freq=rate)
            with open(current_arduino_file, mode="w", encoding="utf-8") as file:
                file.writelines([f"{d}\n" for d in dump])
            with open(current_dump_file, mode="a", encoding="utf-8") as file:
                file.writelines(self._current_log)
            self._current_log = []

        except Exception as e:
            QMessageBox.critical(self, "Erro", f"Falha ao baixar dados de performance: {e}")
            self.logger.error(f"Erro ao baixar dados de performance: {e}")

    def log_performance(self, command: str, address: str, size: str, latency: float):
        #adjust latency value to match arduinos unit usecods
        lat = latency * 1_000_000
        self._current_log.append(f"cmd={command},addr={address},size={size},latency={lat},timestamp={time.perf_counter()}\n")

def main():
    app = QApplication(sys.argv)
    window = DestraGUI()
    window.show()
    sys.exit(app.exec())

if __name__ == "__main__":
    main()
