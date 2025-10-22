@echo off
:: ============================================================================
:: Arquivo: run_destra.bat
:: Autor: Sandro Fadiga
:: Instituição: EESC - USP (Escola de Engenharia de São Carlos)
:: Projeto: DESTRA - DEpurador de Sistemas em Tempo ReAl
:: Data de Criação: 09/01/2025
:: Versão: 1.0
::
:: Descrição:
::   Script de automação para configuração e execução da aplicação DESTRA.
::   Este arquivo realiza as seguintes operações:
::   - Verifica a instalação do Python no sistema
::   - Cria e configura um ambiente virtual Python (venv)
::   - Instala todas as dependências necessárias (PySide6, pyserial, etc.)
::   - Executa a interface gráfica do DESTRA (destra_ui.py)
::
:: Requisitos:
::   - Python 3.8 ou superior instalado no sistema
::   - Arquivo src/requirements.txt com as dependências
::   - Arquivo src/destra_ui.py (aplicação principal)
::
:: Uso:
::   Execute este arquivo com duplo clique ou via linha de comando
:: ============================================================================

setlocal enabledelayedexpansion

echo ========================================
echo   DESTRA - Setup e Execucao Automatica
echo ========================================
echo.

:: Define o nome do ambiente virtual
set VENV_DIR=venv

:: Verifica se Python está instalado
python --version >nul 2>&1
if errorlevel 1 (
    echo [ERRO] Python nao foi encontrado no sistema!
    echo Por favor, instale o Python 3.8 ou superior.
    echo Download: https://www.python.org/downloads/
    pause
    exit /b 1
)

echo [INFO] Python encontrado:
python --version
echo.

:: Verifica se o ambiente virtual já existe
if exist "%VENV_DIR%\Scripts\activate.bat" (
    echo [INFO] Ambiente virtual encontrado em '%VENV_DIR%'
) else (
    echo [INFO] Criando ambiente virtual...
    python -m venv %VENV_DIR%
    if errorlevel 1 (
        echo [ERRO] Falha ao criar ambiente virtual!
        pause
        exit /b 1
    )
    echo [OK] Ambiente virtual criado com sucesso!
)
echo.

:: Ativa o ambiente virtual
echo [INFO] Ativando ambiente virtual...
call %VENV_DIR%\Scripts\activate.bat
if errorlevel 1 (
    echo [ERRO] Falha ao ativar ambiente virtual!
    pause
    exit /b 1
)
echo [OK] Ambiente virtual ativado!
echo.

:: Atualiza o pip
echo [INFO] Atualizando pip...
python -m pip install --upgrade pip >nul 2>&1
if errorlevel 1 (
    echo [AVISO] Nao foi possivel atualizar o pip, continuando...
) else (
    echo [OK] Pip atualizado!
)
echo.

:: Verifica se o arquivo requirements.txt existe
if not exist "requirements.txt" (
    echo [ERRO] Arquivo 'requirements.txt' nao encontrado!
    pause
    exit /b 1
)

:: Instala/atualiza as dependências
echo [INFO] Instalando/atualizando dependencias...
echo.
pip install -r requirements.txt
if errorlevel 1 (
    echo.
    echo [ERRO] Falha ao instalar dependencias!
    echo Verifique se todas as dependencias estao corretas.
    pause
    exit /b 1
)
echo.
echo [OK] Dependencias instaladas com sucesso!
echo.

:: Verifica se o arquivo principal existe
if not exist "src\destra_ui.py" (
    echo [ERRO] Arquivo 'src\destra_ui.py' nao encontrado!
    pause
    exit /b 1
)

:: Executa a aplicação
echo ========================================
echo [INFO] Iniciando DESTRA UI...
echo ========================================
echo.

python src\destra_ui.py

:: Verifica se a aplicação foi executada com sucesso
if errorlevel 1 (
    echo.
    echo [ERRO] A aplicacao encontrou um erro durante a execucao!
    echo Verifique o log acima para mais detalhes.
    pause
) else (
    echo.
    echo [INFO] Aplicacao finalizada.
)

:: Desativa o ambiente virtual
call deactivate >nul 2>&1

echo.
echo Pressione qualquer tecla para sair...
pause >nul
