from flask import Flask, render_template, request, jsonify
from flask_cors import CORS
import MetaTrader5 as mt5
from datetime import datetime, timedelta
import pandas as pd

app = Flask(__name__)
CORS(app)

TIMEFRAME_MAP = {
    "M1": mt5.TIMEFRAME_M1,
    "M5": mt5.TIMEFRAME_M5,
    "M15": mt5.TIMEFRAME_M15,
    "M30": mt5.TIMEFRAME_M30,
    "H1": mt5.TIMEFRAME_H1,
    "H4": mt5.TIMEFRAME_H4,
    "D1": mt5.TIMEFRAME_D1,
}

def init_mt5():
    if not mt5.initialize():
        return False, mt5.last_error()
    return True, None

def shutdown_mt5():
    mt5.shutdown()

@app.route("/")
def index():
    return render_template("index.html")

@app.route("/api/symbols", methods=["GET"])
def get_symbols():
    ok, err = init_mt5()
    if not ok:
        return jsonify({"error": f"MT5 init failed: {err}"}), 500
    symbols = mt5.symbols_get()
    shutdown_mt5()
    if symbols is None:
        return jsonify({"error": "No symbols found"}), 500
    names = sorted([s.name for s in symbols])
    return jsonify({"symbols": names})

@app.route("/api/analyze", methods=["POST"])
def analyze():
    data = request.json
    symbol   = data.get("symbol", "EURUSD")
    tf_str   = data.get("timeframe", "M5")
    days     = int(data.get("days", 10))

    ok, err = init_mt5()
    if not ok:
        return jsonify({"error": f"MT5 init failed: {err}"}), 500

    tf = TIMEFRAME_MAP.get(tf_str)
    if tf is None:
        shutdown_mt5()
        return jsonify({"error": f"Timeframe inválido: {tf_str}"}), 400

    date_to   = datetime.now()
    date_from = date_to - timedelta(days=days)

    rates = mt5.copy_rates_range(symbol, tf, date_from, date_to)
    shutdown_mt5()

    if rates is None or len(rates) == 0:
        return jsonify({"error": f"Sem dados para {symbol} no período solicitado"}), 404

    df = pd.DataFrame(rates)
    df["time"] = pd.to_datetime(df["time"], unit="s")

    candles = []
    green_count = 0
    red_count   = 0

    for _, row in df.iterrows():
        direction = "CALL" if row["close"] > row["open"] else "PUT"
        body_size = abs(row["close"] - row["open"])
        total_range = row["high"] - row["low"]
        body_pct = (body_size / total_range * 100) if total_range > 0 else 0

        candle = {
            "time":      row["time"].strftime("%Y-%m-%d %H:%M"),
            "date":      row["time"].strftime("%d/%m/%Y"),
            "hour":      row["time"].strftime("%H:%M"),
            "open":      round(float(row["open"]), 5),
            "high":      round(float(row["high"]), 5),
            "low":       round(float(row["low"]), 5),
            "close":     round(float(row["close"]), 5),
            "direction": direction,
            "body_size": round(body_size, 5),
            "body_pct":  round(body_pct, 1),
            "volume":    int(row["tick_volume"]),
        }
        candles.append(candle)

        if direction == "CALL":
            green_count += 1
        else:
            red_count += 1

    total = green_count + red_count
    green_pct = round(green_count / total * 100, 1) if total > 0 else 0
    red_pct   = round(red_count   / total * 100, 1) if total > 0 else 0

    # Análise por hora do dia
    df["hour_only"] = pd.to_datetime(df["time"]).dt.hour
    df["direction"] = df.apply(
        lambda r: "CALL" if r["close"] > r["open"] else "PUT", axis=1
    )

    hourly = []
    for h in range(24):
        subset = df[df["hour_only"] == h]
        if len(subset) == 0:
            continue
        calls = (subset["direction"] == "CALL").sum()
        puts  = (subset["direction"] == "PUT").sum()
        total_h = calls + puts
        hourly.append({
            "hour":       f"{h:02d}:00",
            "calls":      int(calls),
            "puts":       int(puts),
            "total":      int(total_h),
            "call_pct":   round(calls / total_h * 100, 1) if total_h > 0 else 0,
            "put_pct":    round(puts  / total_h * 100, 1) if total_h > 0 else 0,
            "bias":       "CALL" if calls >= puts else "PUT",
        })

    # Sequências consecutivas
    max_green_seq = max_red_seq = cur_green = cur_red = 0
    for c in candles:
        if c["direction"] == "CALL":
            cur_green += 1
            cur_red    = 0
            max_green_seq = max(max_green_seq, cur_green)
        else:
            cur_red   += 1
            cur_green  = 0
            max_red_seq = max(max_red_seq, cur_red)

    return jsonify({
        "symbol":        symbol,
        "timeframe":     tf_str,
        "days":          days,
        "date_from":     date_from.strftime("%d/%m/%Y %H:%M"),
        "date_to":       date_to.strftime("%d/%m/%Y %H:%M"),
        "total_candles": total,
        "green_count":   green_count,
        "red_count":     red_count,
        "green_pct":     green_pct,
        "red_pct":       red_pct,
        "max_green_seq": max_green_seq,
        "max_red_seq":   max_red_seq,
        "hourly_stats":  hourly,
        "candles":       candles,
    })

@app.route("/api/filter-signals", methods=["POST"])
def filter_signals():
    """
    Recebe uma lista de sinais no formato 'HH:MM,SYMBOL,DIRECTION,TF'
    e cruza com o histórico do MT5 para calcular a taxa de acerto de cada sinal.
    """
    data      = request.json
    raw_list  = data.get("signals", "")
    days      = int(data.get("days", 30))
    min_score = float(data.get("min_score", 60))  # % mínimo de acerto

    # Parse dos sinais colados
    parsed_signals = []
    for line in raw_list.strip().splitlines():
        line = line.strip()
        if not line:
            continue
        parts = [p.strip() for p in line.split(",")]
        if len(parts) != 4:
            continue
        hour_str, symbol, direction, tf_str = parts
        direction = direction.upper()
        tf_str    = tf_str.upper()
        if direction not in ("CALL", "PUT"):
            continue
        if tf_str not in TIMEFRAME_MAP:
            continue
        parsed_signals.append({
            "hour":      hour_str,   # "10:10"
            "symbol":    symbol.upper(),
            "direction": direction,
            "timeframe": tf_str,
        })

    if not parsed_signals:
        return jsonify({"error": "Nenhum sinal válido encontrado na lista."}), 400

    ok, err = init_mt5()
    if not ok:
        return jsonify({"error": f"MT5 init failed: {err}"}), 500

    date_to   = datetime.now()
    date_from = date_to - timedelta(days=days)

    # Agrupa por (symbol, timeframe) para não buscar dados duplicados
    combos = {}
    for s in parsed_signals:
        key = (s["symbol"], s["timeframe"])
        if key not in combos:
            combos[key] = []
        combos[key].append(s)

    results = []

    for (symbol, tf_str), signals in combos.items():
        tf = TIMEFRAME_MAP[tf_str]
        rates = mt5.copy_rates_range(symbol, tf, date_from, date_to)

        if rates is None or len(rates) == 0:
            for s in signals:
                results.append({**s, "error": "Sem dados históricos"})
            continue

        df = pd.DataFrame(rates)
        df["time"]      = pd.to_datetime(df["time"], unit="s")
        df["direction"] = df.apply(lambda r: "CALL" if r["close"] > r["open"] else "PUT", axis=1)
        df["hhmm"]      = df["time"].dt.strftime("%H:%M")

        for s in signals:
            target_hour = s["hour"]
            target_dir  = s["direction"]

            # Filtra todas as velas naquele exato horário HH:MM
            subset = df[df["hhmm"] == target_hour]
            total_h = len(subset)

            if total_h == 0:
                results.append({**s, "total": 0, "hits": 0, "score": 0.0,
                                 "status": "SEM_DADOS", "error": f"Nenhuma vela em {target_hour}"})
                continue

            hits    = int((subset["direction"] == target_dir).sum())
            misses  = total_h - hits
            score   = round(hits / total_h * 100, 1)

            # Rating qualitativo
            if score >= 75:
                rating = "FORTE"
            elif score >= 60:
                rating = "BOM"
            elif score >= 50:
                rating = "NEUTRO"
            else:
                rating = "FRACO"

            results.append({
                "hour":      target_hour,
                "symbol":    symbol,
                "direction": target_dir,
                "timeframe": tf_str,
                "total":     total_h,
                "hits":      hits,
                "misses":    misses,
                "score":     score,
                "rating":    rating,
                "approved":  score >= min_score,
            })

    shutdown_mt5()

    # Ordena: aprovados primeiro, depois por score desc
    results.sort(key=lambda x: (-int(x.get("approved", False)), -x.get("score", 0)))

    approved  = [r for r in results if r.get("approved")]
    rejected  = [r for r in results if not r.get("approved") and "error" not in r]
    no_data   = [r for r in results if "error" in r]

    return jsonify({
        "days":       days,
        "min_score":  min_score,
        "total_in":   len(parsed_signals),
        "approved":   approved,
        "rejected":   rejected,
        "no_data":    no_data,
    })


if __name__ == "__main__":
    app.run(debug=True, port=5000)
