# MT5 Signal Analyzer

Sistema de análise probabilística de velas do MetaTrader 5 com interface web.

## Requisitos

- Python 3.8+
- MetaTrader 5 instalado e logado no PC
- Windows (a biblioteca MetaTrader5 só funciona no Windows)

## Instalação

```bash
pip install -r requirements.txt
```

## Como usar

1. Abra o MetaTrader 5 e faça login na sua conta
2. Execute o servidor:
   ```bash
   python app.py
   ```
3. Acesse no navegador: http://localhost:5000
4. Preencha o formulário:
   - **Paridade**: ex. EURUSD, GBPUSD, BTCUSD
   - **Timeframe**: M1, M5, M15, M30, H1, H4, D1
   - **Dias**: quantidade de dias retroativos a analisar
5. Clique em **ANALISAR**

## O que o relatório mostra

- **Total de velas** no período
- **Contagem CALL (verde)** vs **PUT (vermelho)** com percentuais
- **Máxima sequência** consecutiva de cada direção
- **Barra de distribuição** visual
- **Estatísticas por hora** — qual horário tem mais viés
- **Top 8 horas** por força de viés
- **Tabela individual** de cada vela com data, hora, sinal, preços
- **Exportar CSV** e **Copiar relatório** em texto

## Lógica dos sinais

- **CALL** = fechamento > abertura (vela verde)
- **PUT**  = fechamento < abertura (vela vermelha)
- Formato: `10:00, EURUSD, CALL, M5`
