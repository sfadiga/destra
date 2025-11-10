#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Arquivo: performance_tests.py
Autor: Sandro Fadiga
Instituição: EESC - USP (Escola de Engenharia de São Carlos)
Projeto: DESTRA - DEpurador de Sistemas em Tempo ReAl
Data de Criação: 09/01/2025
Versão: 1.0

Descrição:
    Módulo de testes de performance para análise de latência, jitter e throughput
    do protocolo DESTRA. Gera métricas estatísticas e visualizações para análise
    de desempenho em tempo real.

Funcionalidades:
    - Medição de latência (Round-Trip Time)
    - Cálculo de jitter
    - Análise estatística (média, desvio padrão, percentis)
    - Geração de gráficos
    - Exportação de dados para análise externa
    - Testes de stress e carga

Dependências:
    - numpy: Cálculos estatísticos
    - matplotlib: Visualização de dados
    - pandas: Manipulação de dados
    - destra: Protocolo de comunicação

Licença: MIT
"""
import sys
from datetime import datetime
import re
import time
import numpy as np
import pandas as pd
import matplotlib.pyplot as plt
from typing import List, Dict, Tuple, Optional
import json
from pathlib import Path
from typing import List, Dict

from destra import DestraProtocol
from logger_config import DestraLogger


class PerformanceMetrics:
    """Classe para coletar e analisar métricas de performance"""

    def __init__(self):
        self.latencies: List[float] = []
        self.timestamps: List[float] = []
        self.jitter_values: List[float] = []
        self.errors: List[Dict[str, any]] = []
        self.test_start_time = None
        self.test_end_time = None

        # Configurar logger
        logger_manager = DestraLogger()
        self.logger = logger_manager.logger.getChild("Performance")

    def add_measurement(
        self,
        latency: float,
        timestamp: float,
        success: bool = True,
        error_msg: str = "",
    ):
        """Adicionar uma medição de latência"""
        self.latencies.append(latency)
        self.timestamps.append(timestamp)

        # Calcular jitter (variação entre latências consecutivas)
        if len(self.latencies) > 1:
            jitter = abs(self.latencies[-1] - self.latencies[-2])
            self.jitter_values.append(jitter)

        if not success:
            self.errors.append(
                {"timestamp": timestamp, "latency": latency, "error": error_msg}
            )

    def calculate_statistics(self) -> Dict[str, any]:
        """Calcular estatísticas das medições"""
        if not self.latencies:
            return {}

        latencies_ms = [l * 1000 for l in self.latencies]  # Converter para ms
        jitter_ms = [j * 1000 for j in self.jitter_values] if self.jitter_values else []

        stats = {
            "total_de_medidas": len(self.latencies),
            "medidas_bem_sucedidas": len(self.latencies) - len(self.errors),
            "taxa_de_erro": len(self.errors) / len(self.latencies) * 100
            if self.latencies
            else 0,
            "latencia": {
                "media_ms": float(np.mean(latencies_ms)),
                "mediana_ms": float(np.median(latencies_ms)),
                "desvio_padrao_ms": float(np.std(latencies_ms)),
                "min_ms": float(np.min(latencies_ms)),
                "max_ms": float(np.max(latencies_ms)),
                "p95_ms": float(np.percentile(latencies_ms, 95)),
                "p99_ms": float(np.percentile(latencies_ms, 99)),
            },
        }

        if jitter_ms:
            stats["jitter"] = {
                "media_ms": float(np.mean(jitter_ms)),
                "mediana_ms": float(np.median(jitter_ms)),
                "desvio_padrao_ms": float(np.std(jitter_ms)),
                "min_ms": float(np.min(jitter_ms)),
                "max_ms": float(np.max(jitter_ms)),
            }

        return stats

    def export_to_csv(self, filename: str):
        """Exportar dados para arquivo CSV"""
        df = pd.DataFrame(
            {
                "tempo": self.timestamps,
                "latencia_ms": [l * 1000 for l in self.latencies],
                "jitter_ms": [j * 1000 for j in self.jitter_values]
                + [0],  # Adicionar 0 para primeira medição
            }
        )
        df.to_csv(filename, index=False)
        self.logger.info(f"Dados exportados para {filename}")

    def plot_results(self, save_path: Optional[str] = None):
        """Gerar gráficos de visualização"""
        fig, axes = plt.subplots(2, 2, figsize=(12, 8))

        # Gráfico 1: Latência ao longo do tempo
        axes[0, 0].plot(
            self.timestamps, [l * 1000 for l in self.latencies], "b-", alpha=0.7
        )
        axes[0, 0].set_xlabel("Tempo (s)")
        axes[0, 0].set_ylabel("Latência (ms)")
        axes[0, 0].set_title("Latência ao Longo do Tempo")
        axes[0, 0].grid(True, alpha=0.3)

        # Gráfico 2: Histograma de latência
        axes[0, 1].hist(
            [l * 1000 for l in self.latencies], bins=50, edgecolor="black", alpha=0.7
        )
        axes[0, 1].set_xlabel("Latência (ms)")
        axes[0, 1].set_ylabel("Frequência")
        axes[0, 1].set_title("Distribuição de Latência")
        axes[0, 1].grid(True, alpha=0.3)

        # Gráfico 3: Jitter ao longo do tempo
        if self.jitter_values:
            axes[1, 0].plot(
                self.timestamps[1:],
                [j * 1000 for j in self.jitter_values],
                "r-",
                alpha=0.7,
            )
            axes[1, 0].set_xlabel("Tempo (s)")
            axes[1, 0].set_ylabel("Jitter (ms)")
            axes[1, 0].set_title("Jitter ao Longo do Tempo")
            axes[1, 0].grid(True, alpha=0.3)

        # Gráfico 4: Boxplot comparativo
        data_to_plot = [[l * 1000 for l in self.latencies]]
        labels = ["Latência"]
        if self.jitter_values:
            data_to_plot.append([j * 1000 for j in self.jitter_values])
            labels.append("Jitter")
        axes[1, 1].boxplot(data_to_plot, tick_labels=labels)
        axes[1, 1].set_ylabel("Tempo (ms)")
        axes[1, 1].set_title("Análise Estatística")
        axes[1, 1].grid(True, alpha=0.3)

        plt.tight_layout()

        if save_path:
            plt.savefig(save_path, dpi=300, bbox_inches="tight")
            self.logger.info(f"Gráficos salvos em {save_path}")
        else:
            plt.show()
        return fig


class PerformanceTester:
    """Classe principal para executar testes de performance"""

    def __init__(self, port: str = None, baudrate: int = 115200):
        self.protocol = DestraProtocol(port=port, baudrate=baudrate)
        self.metrics = PerformanceMetrics()

        # Configurar logger
        logger_manager = DestraLogger()
        self.logger = logger_manager.logger.getChild("Tester")

    def connect(self) -> bool:
        """Conectar ao Arduino"""
        return self.protocol.connect()

    def disconnect(self):
        """Desconectar do Arduino"""
        self.protocol.disconnect()

    def test_single_peek(self, address: int, size: int) -> Tuple[float, bool]:
        """Testar um único comando peek e medir latência"""
        start_time = time.perf_counter()

        try:
            data = self.protocol.peek(address, size)
            end_time = time.perf_counter()
            latency = end_time - start_time
            success = data is not None

            return latency, success
        except Exception as e:
            end_time = time.perf_counter()
            latency = end_time - start_time
            self.logger.error(f"Erro no peek: {e}")
            return latency, False

    def test_single_poke(
        self, address: int, size: int, value: int
    ) -> Tuple[float, bool]:
        """Testar um único comando poke e medir latência"""
        start_time = time.perf_counter()

        try:
            success = self.protocol.poke(address, size, value)
            end_time = time.perf_counter()
            latency = end_time - start_time

            return latency, success
        except Exception as e:
            end_time = time.perf_counter()
            latency = end_time - start_time
            self.logger.error(f"Erro no poke: {e}")
            return latency, False

    def run_latency_test(
        self, num_samples: int = 100, address: int = 0x0100, size: int = 4
    ) -> Dict[str, any]:
        """Executar teste de latência com múltiplas amostras"""
        self.logger.info(f"Iniciando teste de latência: {num_samples} amostras")
        self.metrics = PerformanceMetrics()  # Reset metrics
        self.metrics.test_start_time = time.time()

        for i in range(num_samples):
            timestamp = time.time() - self.metrics.test_start_time
            latency, success = self.test_single_peek(address, size)
            self.metrics.add_measurement(latency, timestamp, success)

            # Log de progresso a cada 10 amostras
            if (i + 1) % 10 == 0:
                self.logger.debug(f"Progresso: {i + 1}/{num_samples}")

        self.metrics.test_end_time = time.time()
        stats = {}
        stats["teste"] = "Latencia"
        stats.update(self.metrics.calculate_statistics())

        self.logger.info("Teste de latência concluído")

        return stats

    def run_stress_test(
        self,
        duration_seconds: int = 60,
        frequency_hz: int = 100,
        address: int = 0x0100,
        size: int = 4,
    ) -> Dict[str, any]:
        """Executar teste de stress com alta frequência de comandos"""
        self.logger.info(
            f"Iniciando teste de stress: {duration_seconds}s @ {frequency_hz}Hz"
        )
        self.metrics = PerformanceMetrics()  # Reset metrics
        self.metrics.test_start_time = time.time()

        interval = 1.0 / frequency_hz
        end_time = time.time() + duration_seconds

        while time.time() < end_time:
            timestamp = time.time() - self.metrics.test_start_time
            latency, success = self.test_single_peek(address, size)
            self.metrics.add_measurement(latency, timestamp, success)

            # Aguardar para manter a frequência
            time.sleep(max(0, interval - latency))

        self.metrics.test_end_time = time.time()
        stats = {}
        stats["teste"] = "Estress"
        stats.update(self.metrics.calculate_statistics())

        self.logger.info("Teste de stress concluído")
        return stats

    def run_burst_test(
        self,
        burst_size: int = 10,
        num_bursts: int = 10,
        delay_between_bursts: float = 1.0,
        address: int = 0x0100,
        size: int = 4,
    ) -> Dict[str, any]:
        """Executar teste de burst - rajadas de comandos"""
        self.logger.info(
            f"Iniciando teste de burst: {num_bursts} bursts de {burst_size} comandos"
        )
        self.metrics = PerformanceMetrics()  # Reset metrics
        self.metrics.test_start_time = time.time()

        for burst_num in range(num_bursts):
            # Executar burst
            for _ in range(burst_size):
                timestamp = time.time() - self.metrics.test_start_time
                latency, success = self.test_single_peek(address, size)
                self.metrics.add_measurement(latency, timestamp, success)

            # Delay entre bursts
            if burst_num < num_bursts - 1:
                time.sleep(delay_between_bursts)

        self.metrics.test_end_time = time.time()
        stats = {}
        stats["teste"] = "Burst"
        stats.update(self.metrics.calculate_statistics())

        self.logger.info("Teste de burst concluído")

        return stats

    def dump_embedded_performance_data(self, associated_test: str) -> dict:
        self.logger.info(f"Iniciando download de dados de performance para: {associated_test}")
        payload = self.protocol.performance()
        #print(payload)
        # converte para formato texto a ser usado com regex
        payload_csv = "\n".join([str(p) for p in payload])
        
        # --- 1. Parse do payload ---
        pattern = re.compile(
            r"frame_counter:\s*(\d+),\s*frame_rate:(\d+),\s*frame_jitter_us:(\d+),\s*command_sequence:(\d+),\s*command_counter_delta:(\d+),\s*command_process_time_us:(\d+)"
        )

        data = [tuple(map(int, m.groups())) for m in pattern.finditer(payload_csv)]
        if not data:
            self.logger.warning("Nenhum dado de performance encontrado no payload.")
            return None

        arr = np.array(data, dtype=int)
        frame_counter = arr[:, 0]
        frame_rate = arr[:, 1]
        frame_jitter_us = arr[:, 2]
        command_sequence = arr[:, 3]
        command_counter_delta = arr[:, 4]
        command_process_time_us = arr[:, 5]

        # --- 2. Conversão µs → ms ---
        frame_jitter_ms = frame_jitter_us / 1000.0
        command_process_time_ms = command_process_time_us / 1000.0

        # --- 3. Estatísticas ---
        def basic_stats(values_ms):
            return {
                "media_ms": float(np.mean(values_ms)),
                "mediana_ms": float(np.median(values_ms)),
                "desvio_padrao_ms": float(np.std(values_ms)),
                "min_ms": float(np.min(values_ms)),
                "max_ms": float(np.max(values_ms)),
                "p95_ms": float(np.percentile(values_ms, 95)),
                "p99_ms": float(np.percentile(values_ms, 99)),
            }

        stats = {
            "dados_embarcados_para_teste_de": associated_test,
            "total_de_amostras": len(frame_counter),
            "frame_jitter": basic_stats(frame_jitter_ms),
            "frame_rate": {
                "media_fps": float(np.mean(frame_rate)),
                "mediana_fps": float(np.median(frame_rate)),
                "desvio_padrao_ms": float(np.std(frame_rate)),
                "min_fps": float(np.min(frame_rate)),
                "max_fps": float(np.max(frame_rate)),
            },
            "command_process_time": basic_stats(command_process_time_ms),
        }

        # --- 4. Análise de sequência / desvio ---
        def find_sequence_anomalies(seq):
            diffs = np.diff(seq)
            expected = 1
            anomalies = np.where(diffs != expected)[0]
            return anomalies.tolist() if len(anomalies) > 0 else 0

        sequence_issues = {
            "gaps_frame_counter": find_sequence_anomalies(frame_counter),
            "gaps_command_sequence": find_sequence_anomalies(command_sequence),
            "anomalias_command_counter_delta": np.where(command_counter_delta != 0)[0].tolist()
                if np.any(command_counter_delta != 0) else 0,
        }

        stats["analise_de_sequencia"] = sequence_issues
        return stats

def genetate_reports(test_name: str, tester_ref, test_dump, embedded_dump):
    curr_dir = Path.cwd()
    test_results_path = curr_dir.parent / Path("tests")

    # Teste de latência
    # Criar arquivo Markdown
    timestamp_str = datetime.now().strftime("%Y%m%d_%H%M%S")
    report_file = test_results_path / Path(f"{test_name}_{timestamp_str}.md")

    with open(report_file.resolve(), "w", encoding="utf-8") as file:
        file.write(f"# 📊 Relatório de Testes {test_name}\n\n")
        file.write("## 🧪 Dados de Performance Externos\n")
        file.write("```json\n")
        file.write(json.dumps(test_dump, indent=2))
        file.write("\n```\n\n")
        file.write("## ⚙️ Dados de Performance Embarcada\n")
        file.write("```json\n")
        file.write(json.dumps(embedded_dump, indent=2))
        file.write("\n```\n")

    plot_file = test_results_path / Path(f"{test_name}_{timestamp_str}.png")
    tester_ref.metrics.plot_results(plot_file)


def main():
    """Função principal para executar testes de performance e gerar relatório Markdown"""

    # Verificar argumentos
    port = "COM5"
    if len(sys.argv) > 1:
        port = sys.argv[1]

    # Criar tester
    tester = PerformanceTester(port=port)

    # Conectar
    if not tester.connect():
        print("**Falha ao conectar ao Arduino!**\n")
        return

    try:
        # Teste de latência
        stats = tester.run_latency_test(num_samples=100)
        embed = tester.dump_embedded_performance_data("Latencia")
        genetate_reports("Latencia", tester, stats, embed)

        # Teste de stress
        stats = tester.run_stress_test(duration_seconds=10)
        embed = tester.dump_embedded_performance_data("Estresse")
        genetate_reports("Estresse", tester, stats, embed)

        # Teste de burst
        stats = tester.run_burst_test()
        embed = tester.dump_embedded_performance_data("Burst")
        genetate_reports("Burst", tester, stats, embed)

    except KeyboardInterrupt:
        print("\n**Teste interrompido pelo usuário**\n")
    except Exception as e:
        import traceback
        traceback.print_exc()
        print(f"\n**Erro durante o teste: {e}**\n")
    finally:
        tester.disconnect()

if __name__ == "__main__":
    main()
