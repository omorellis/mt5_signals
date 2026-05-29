@echo off
echo ================================================
echo  MT5 Signal Analyzer - Gerador de Executavel
echo ================================================
echo.

python --version >nul 2>&1
if errorlevel 1 (
    echo [ERRO] Python nao encontrado.
    pause & exit /b 1
)

echo [1/4] Instalando dependencias...
pip install -r requirements.txt --quiet

echo [2/4] Instalando PyInstaller...
pip install pyinstaller --quiet

echo [3/4] Limpando build anterior...
if exist build   rmdir /s /q build
if exist dist    rmdir /s /q dist

echo [4/4] Gerando executavel...
pyinstaller mt5_signals.spec --clean --noconfirm

if errorlevel 1 (
    echo.
    echo [ERRO] Falha ao gerar o executavel.
    pause & exit /b 1
)

echo.
echo ================================================
echo  SUCESSO! dist\MT5SignalAnalyzer.exe
echo ================================================
pause
