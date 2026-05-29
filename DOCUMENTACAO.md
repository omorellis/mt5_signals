# 📊 MT5 Signal Analyzer — Documentação Completa

> Sistema de análise probabilística de velas do MetaTrader 5 com interface web.  
> Identifica padrões históricos de direção (CALL/PUT) por horário e filtra sinais com base em taxa de acerto real.

---

## Sumário

1. [O que é o sistema](#1-o-que-é-o-sistema)
2. [Requisitos](#2-requisitos)
3. [Instalação](#3-instalação)
4. [Como iniciar](#4-como-iniciar)
5. [Aba Analisador MT5](#5-aba-analisador-mt5)
6. [Entendendo o Relatório](#6-entendendo-o-relatório)
7. [Aba Filtro de Sinais](#7-aba-filtro-de-sinais)
8. [Exportação de Dados](#8-exportação-de-dados)
9. [Lógica dos Sinais](#9-lógica-dos-sinais)
10. [Perguntas Frequentes](#10-perguntas-frequentes)

---

## 1. O que é o sistema

O **MT5 Signal Analyzer** conecta diretamente ao MetaTrader 5 instalado no seu computador e extrai dados históricos de candles para gerar um relatório probabilístico.

O objetivo é responder perguntas como:

- *Nos últimos 30 dias, às 10:10, o EURUSD subiu ou caiu mais vezes?*
- *Quais horários têm o viés mais forte e consistente?*
- *Essa lista de sinais que tenho é confiável historicamente?*

O sistema **não gera sinais sozinho** — ele analisa o histórico real do mercado e te mostra a probabilidade de cada direção em cada horário, para que você tome decisões mais embasadas.

---

## 2. Requisitos

| Item | Detalhe |
|------|---------|
| Sistema Operacional | **Windows** (obrigatório — a biblioteca MT5 só funciona no Windows) |
| Python | Versão 3.8 ou superior |
| MetaTrader 5 | Instalado e com conta logada |
| Navegador | Qualquer navegador moderno (Chrome, Edge, Firefox) |

---

## 3. Instalação

**Passo 1 — Instale as dependências Python:**

```bash
pip install -r requirements.txt
```

As bibliotecas instaladas são:

| Biblioteca | Função |
|-----------|--------|
| `flask` | Servidor web local |
| `flask-cors` | Comunicação entre frontend e backend |
| `MetaTrader5` | Conexão com o terminal MT5 |
| `pandas` | Processamento dos dados de candles |

---

## 4. Como iniciar

1. Abra o **MetaTrader 5** e faça login na sua conta normalmente
2. Abra o terminal (Prompt de Comando) na pasta do projeto
3. Execute:

```bash
python app.py
```

4. Você verá a mensagem:
```
* Running on http://127.0.0.1:5000
```

5. Abra o navegador e acesse: **http://localhost:5000**

> ⚠️ Mantenha o terminal aberto enquanto estiver usando o sistema. Fechar o terminal encerra o servidor.

---

## 5. Aba Analisador MT5

Essa é a tela principal. Preencha o formulário no topo e clique em **▶ ANALISAR**.

### Campos do formulário

| Campo | O que preencher | Exemplo |
|-------|----------------|---------|
| **Paridade** | Símbolo do ativo exatamente como aparece no MT5 | `EURUSD`, `GBPUSD`, `BTCUSD` |
| **Timeframe** | Período de cada candle | `M5` (5 minutos) |
| **Dias analisados** | Quantos dias retroativos buscar | `10`, `30`, `90` |

> 💡 O campo **Paridade** tem autocomplete — ao digitar, sugestões de símbolos disponíveis na sua corretora aparecem automaticamente.

### Timeframes disponíveis

| Opção | Significado |
|-------|------------|
| M1 | 1 minuto |
| M5 | 5 minutos |
| M15 | 15 minutos |
| M30 | 30 minutos |
| H1 | 1 hora |
| H4 | 4 horas |
| D1 | Diário |

---

## 6. Entendendo o Relatório

Após clicar em **ANALISAR**, o relatório é exibido em seções:

---

### 6.1 Barra de Informações

```
SÍMBOLO: EURUSD  |  TIMEFRAME: M5  |  PERÍODO: 15/05/2025 → 25/05/2025  |  TOTAL: 1.440 velas
```

Mostra um resumo rápido do que foi analisado.

---

### 6.2 Cards de Estatísticas

Quatro cards principais:

| Card | O que mostra |
|------|-------------|
| **VELAS VERDES (CALL)** | Quantidade e % de candles de alta no período |
| **VELAS VERMELHAS (PUT)** | Quantidade e % de candles de baixa no período |
| **MÁX. SEQUÊNCIA CALL** | Maior número de candles verdes consecutivos encontrado |
| **MÁX. SEQUÊNCIA PUT** | Maior número de candles vermelhos consecutivos encontrado |

---

### 6.3 Barra de Distribuição CALL / PUT

Barra visual que mostra a proporção entre CALL e PUT de forma imediata.

- Lado **verde** = percentual de CALL
- Lado **vermelho** = percentual de PUT

Se a barra estiver muito equilibrada (50/50), o ativo não tem viés claro no período. Se estiver desbalanceada, há uma tendência histórica.

---

### 6.4 Estatísticas por Hora

Tabela que quebra a análise **hora a hora** (00:00 até 23:00):

| Coluna | Significado |
|--------|------------|
| **HORA** | Hora do dia (ex: `14:00`) |
| **CALL** | Quantidade de velas de alta nessa hora |
| **PUT** | Quantidade de velas de baixa nessa hora |
| **VIÉS** | Direção predominante nessa hora |
| **DIST** | Barra visual proporcional ao % de CALL — quanto mais preenchida, maior o viés de alta |

> 💡 Use essa tabela para identificar em quais horários o mercado tem comportamento mais previsível.

---

### 6.5 Top Horas por Viés

Ranking das **8 horas com o viés mais forte** do dia.

Cada linha mostra:
- O horário
- Uma barra de intensidade
- O percentual e a direção dominante (`▲ 74%` para CALL ou `▼ 68%` para PUT)

**Como interpretar:** Um horário com `▲ 78%` significa que, historicamente, 78% das vezes que esse candle abriu naquele horário, ele fechou em alta. Quanto mais distante de 50%, mais forte e confiável o viés.

---

### 6.6 Tabela de Velas Individuais

Lista completa de cada candle analisado, no formato:

```
#  |  DATA        |  HORA  |  SÍMBOLO  |  SINAL  |  TF  |  ABERTURA  |  FECHAMENTO  |  VARIAÇÃO  |  CORPO %
1  |  15/05/2025  |  08:00 |  EURUSD   |  CALL   |  M5  |  1.08432   |  1.08461     |  +0.00029  |  72.3%
```

**Filtros disponíveis:**

| Botão | Função |
|-------|--------|
| TODAS | Mostra todos os candles |
| ▲ CALL | Mostra apenas candles de alta |
| ▼ PUT | Mostra apenas candles de baixa |
| 🔍 filtrar hora... | Digita um horário (ex: `08:`) para ver só aquela janela |

---

## 7. Aba Filtro de Sinais

Acesse clicando em **⬡ FILTRO DE SINAIS** no menu superior.

### Para que serve

Você já tem uma lista de sinais — talvez gerada por outro sistema, grupo de sinais ou análise própria. O Filtro valida cada sinal contra o histórico real do MT5 e mostra quais têm taxa de acerto suficiente para serem confiáveis.

### Como usar

**Passo 1 — Cole sua lista de sinais** na caixa de texto, um por linha, no formato:

```
HH:MM,SIMBOLO,DIREÇÃO,TIMEFRAME
```

Exemplo:
```
10:10,EURUSD,CALL,M5
14:30,EURUSD,PUT,M5
08:00,GBPUSD,CALL,M15
09:05,EURUSD,CALL,M5
16:00,USDJPY,PUT,H1
```

**Passo 2 — Configure os parâmetros:**

| Parâmetro | Função | Recomendação |
|-----------|--------|-------------|
| **Dias de histórico** | Quantos dias retroativos usar para validar | 30 dias ou mais para maior confiabilidade |
| **Score mínimo** | Percentual mínimo de acerto para aprovar o sinal | 60% é conservador, 70%+ é mais seguro |

**Passo 3 — Clique em ⬡ FILTRAR**

### Entendendo os Resultados

**Cards de resumo:**

| Card | Significado |
|------|-------------|
| ✅ APROVADOS | Sinais com acerto ≥ score mínimo definido |
| ❌ REPROVADOS | Sinais abaixo do score mínimo |
| TOTAL | Total de sinais analisados |

**Cards individuais de cada sinal:**

```
10:10  |  EURUSD  M5  |  ▲ CALL  |  ████████░░  |  ◎ 74%  |  FORTE
                         22 acertos de 30 velas históricas
```

| Elemento | Significado |
|----------|-------------|
| Horário | A hora exata do sinal |
| Ativo + TF | Símbolo e timeframe |
| Tag CALL/PUT | Direção do sinal |
| Barra | Proporção visual do acerto |
| Anel com % | Score de acerto histórico |
| Badge de rating | Classificação qualitativa |

### Ratings de Qualidade

| Rating | Score | Interpretação |
|--------|-------|--------------|
| **FORTE** | ≥ 75% | Sinal muito consistente historicamente |
| **BOM** | ≥ 60% | Bom histórico, vale operar com atenção |
| **NEUTRO** | ≥ 50% | Ligeiramente favorável, mas sem convicção |
| **FRACO** | < 50% | Histórico contrário à direção do sinal — evitar |

> ⚠️ Um sinal **FRACO** significa que historicamente a direção oposta aconteceu mais vezes. Use com muito cuidado ou descarte.

---

## 8. Exportação de Dados

Ambas as abas oferecem opções de exportação:

### No Analisador MT5

| Botão | O que faz |
|-------|----------|
| **⬇ EXPORTAR CSV** | Baixa todas as velas em arquivo `.csv` compatível com Excel |
| **⎘ COPIAR RELATÓRIO** | Copia o relatório em texto para a área de transferência |

O texto copiado segue o formato:
```
10:00, EURUSD, CALL, M5
10:05, EURUSD, PUT, M5
10:10, EURUSD, CALL, M5
```

### No Filtro de Sinais

| Botão | O que faz |
|-------|----------|
| **⬇ EXPORTAR APROVADOS CSV** | Baixa apenas os sinais aprovados com score e rating |
| **⎘ COPIAR APROVADOS** | Copia os sinais aprovados com score para a área de transferência |

---

## 9. Lógica dos Sinais

### Definição de CALL e PUT

```
CALL (verde) → fechamento > abertura   (candle subiu)
PUT  (vermelho) → fechamento < abertura  (candle caiu)
```

Candles de doji (fechamento = abertura) são classificados como **PUT** por padrão.

### Como o Score é calculado

```
Score = (acertos no horário ÷ total de velas no horário) × 100
```

**Exemplo prático:**

> Sinal: `10:10, EURUSD, CALL, M5` | Histórico: 30 dias

O sistema busca todas as velas de EURUSD M5 que abriram às **10:10** nos últimos 30 dias.  
Se encontrou 20 velas e 15 delas fecharam em alta → Score = `15 ÷ 20 × 100 = 75%` → Rating: **FORTE**

### Granularidade do horário

O filtro usa o horário **exato ao minuto** (`HH:MM`). Um sinal de `10:10` só valida velas que abriram às `10:10`, não às `10:05` ou `10:15`.

---

## 10. Perguntas Frequentes

**O sistema funciona com qualquer corretora?**  
Sim, desde que a corretora esteja configurada no MetaTrader 5. Os símbolos disponíveis dependem da sua corretora.

**Por que o sistema retorna erro "Sem dados"?**  
Pode ocorrer quando o símbolo digitado não existe na corretora, o MT5 não está aberto, ou o período solicitado não tem dados disponíveis (ex: finais de semana, feriados).

**Qual o período ideal de dias para analisar?**  
- **10–15 dias**: Visão recente do comportamento do ativo
- **30 dias**: Equilíbrio entre recente e estatisticamente relevante *(recomendado)*
- **60–90 dias**: Mais dados, mas inclui condições de mercado mais antigas

**O sistema garante lucro nas operações?**  
Não. O sistema mostra probabilidades históricas, não garante que o padrão se repetirá. Use como uma ferramenta de apoio à decisão, sempre combinando com sua própria análise.

**Posso usar em ativos além de Forex?**  
Sim. Funciona com qualquer ativo disponível no seu MT5: índices, commodities, criptomoedas, ações — desde que o símbolo esteja disponível na sua corretora.

**O campo "Paridade" aceita qualquer símbolo?**  
O sistema tenta buscar o símbolo exatamente como digitado. Se sua corretora usa sufixos como `EURUSDm` ou `EURUSD.raw`, use o nome exato. O autocomplete ajuda com isso.

---

*Documentação gerada para MT5 Signal Analyzer v1.0*

---

## 11. Gerando o Executável (.exe)

Para distribuir ou usar o sistema sem precisar do terminal Python, gere um `.exe` com o PyInstaller.

### Passo a passo

**1. Na pasta do projeto, execute o arquivo de build:**

```
build.bat
```

Ou manualmente no terminal:

```bash
pip install pyinstaller
pyinstaller mt5_signals.spec --clean --noconfirm
```

**2. Aguarde** — o processo leva alguns minutos na primeira vez.

**3. O executável estará em:**

```
dist\MT5SignalAnalyzer.exe
```

### O que acontece ao executar o .exe

1. O servidor Flask inicia internamente (sem janela preta)
2. O navegador padrão abre automaticamente em `http://localhost:5000`
3. O sistema está pronto para usar

### Observações importantes

| Item | Detalhe |
|------|---------|
| **MT5 ainda precisa estar aberto** | O `.exe` não substitui o MetaTrader 5 — ele só elimina a necessidade do terminal Python |
| **Tamanho do .exe** | Entre 30–60 MB (inclui Python + bibliotecas embutidas) |
| **Compatibilidade** | Funciona em qualquer Windows 10/11, mesmo sem Python instalado |
| **Antivírus** | Alguns antivírus podem alertar sobre o `.exe` gerado pelo PyInstaller — é falso positivo, pode liberar |
| **UPX (opcional)** | Instalar o [UPX](https://upx.github.io/) reduz o tamanho do `.exe` em ~30% |

