from flask import Flask, render_template, request, jsonify
from flask_cors import CORS
import MetaTrader5 as mt5
from datetime import datetime, timedelta
import pandas as pd
import numpy as np

app = Flask(__name__)
CORS(app)

TIMEFRAME_MAP = {
    "M1":  mt5.TIMEFRAME_M1,
    "M5":  mt5.TIMEFRAME_M5,
    "M15": mt5.TIMEFRAME_M15,
    "M30": mt5.TIMEFRAME_M30,
    "H1":  mt5.TIMEFRAME_H1,
    "H4":  mt5.TIMEFRAME_H4,
    "D1":  mt5.TIMEFRAME_D1,
}
DAYS_PT = ["Segunda", "Terça", "Quarta", "Quinta", "Sexta", "Sábado", "Domingo"]

def init_mt5():
    if not mt5.initialize():
        return False, mt5.last_error()
    return True, None

def shutdown_mt5():
    mt5.shutdown()

# ── INDICADORES ───────────────────────────────────────────────────────────────

def calc_rsi(series, period=14):
    delta    = series.diff()
    gain     = delta.clip(lower=0)
    loss     = -delta.clip(upper=0)
    avg_gain = gain.ewm(com=period-1, min_periods=period).mean()
    avg_loss = loss.ewm(com=period-1, min_periods=period).mean()
    rs  = avg_gain / avg_loss.replace(0, np.nan)
    return (100 - (100 / (1 + rs))).fillna(50)

def calc_ema(series, period):
    return series.ewm(span=period, adjust=False).mean()

def calc_volume_ratio(volume_series, period=20):
    avg = volume_series.rolling(period).mean()
    return (volume_series / avg.replace(0, np.nan)).fillna(1.0)

def enrich_dataframe(df, min_body_pct=0.0):
    """
    Enriquece o DataFrame com indicadores e filtra velas doji se min_body_pct > 0.
    min_body_pct: percentual mínimo do corpo em relação ao range total (0-100).
    """
    df = df.copy()
    df["body_size"]   = (df["close"] - df["open"]).abs()
    df["total_range"] = df["high"] - df["low"]
    df["body_pct"]    = np.where(
        df["total_range"] > 0,
        df["body_size"] / df["total_range"] * 100,
        0
    )
    # Filtro de corpo mínimo — remove doji e velas fracas
    if min_body_pct > 0:
        df = df[df["body_pct"] >= min_body_pct].copy()

    if len(df) == 0:
        return df

    df["rsi"]       = calc_rsi(df["close"], 14)
    df["ema9"]      = calc_ema(df["close"], 9)
    df["ema21"]     = calc_ema(df["close"], 21)
    df["ema50"]     = calc_ema(df["close"], 50)
    df["vol_ratio"] = calc_volume_ratio(df["tick_volume"], 20)
    df["direction"] = np.where(df["close"] > df["open"], "CALL", "PUT")
    df["hhmm"]      = df["time"].dt.strftime("%H:%M")
    df["weekday"]   = df["time"].dt.weekday
    df["hour_only"] = df["time"].dt.hour
    df["week_num"]  = df["time"].dt.isocalendar().week.astype(int)
    df["year_week"] = df["time"].dt.strftime("%Y-W%W")
    return df

def composite_score(hist_score, rsi_avg, ema_aligned, vol_avg, direction):
    rsi_score = max(0, min(100, (70 - rsi_avg) / 20 * 100)) if direction == "CALL" \
                else max(0, min(100, (rsi_avg - 30) / 20 * 100))
    ema_score = ema_aligned * 100
    vol_score = min(100, vol_avg * 50)
    return round(hist_score*0.40 + rsi_score*0.25 + ema_score*0.20 + vol_score*0.15, 1)

def rating_from_score(score):
    if score >= 75: return "FORTE"
    if score >= 60: return "BOM"
    if score >= 50: return "NEUTRO"
    return "FRACO"

# ── ANÁLISE DE SEQUÊNCIAS ─────────────────────────────────────────────────────

def calc_sequence_stats(directions):
    """
    Analisa padrões de sequência:
    Após N velas iguais consecutivas, qual a probabilidade da próxima ser diferente?
    """
    stats = {}   # key: (after_n, direction) → {same, diff, total}
    seq_len = 1
    for i in range(1, len(directions)):
        prev = directions[i-1]
        curr = directions[i]
        # Conta sequência atual
        if i >= 2 and directions[i-2] == prev:
            seq_len += 1
        else:
            seq_len = 1

        for n in range(1, min(seq_len+1, 8)):
            key = (n, prev)
            if key not in stats:
                stats[key] = {"same": 0, "diff": 0}
            if curr == prev:
                stats[key]["same"] += 1
            else:
                stats[key]["diff"] += 1

    result = []
    for (n, direction), v in stats.items():
        total = v["same"] + v["diff"]
        if total < 3:
            continue
        diff_pct = round(v["diff"] / total * 100, 1)
        result.append({
            "after_n":       n,
            "direction":     direction,
            "next_opposite": diff_pct,
            "next_same":     round(v["same"] / total * 100, 1),
            "total_cases":   total,
            "label":         f"Após {n}x {direction} seguidas",
        })
    result.sort(key=lambda x: (-x["after_n"], x["direction"]))
    return result

# ── CONSISTÊNCIA SEMANAL ──────────────────────────────────────────────────────

def calc_weekly_consistency(df, hour_str, direction):
    """
    Para cada semana no histórico, verifica se aquele horário acertou a direção.
    Retorna % de semanas onde o sinal foi correto.
    """
    subset = df[df["hhmm"] == hour_str].copy()
    if len(subset) == 0:
        return 0.0, 0

    weeks = subset.groupby("year_week").apply(
        lambda g: (g["direction"] == direction).any()
    )
    hit_weeks  = int(weeks.sum())
    total_weeks = len(weeks)
    consistency = round(hit_weeks / total_weeks * 100, 1) if total_weeks > 0 else 0.0
    return consistency, total_weeks

# ── ROTAS ─────────────────────────────────────────────────────────────────────

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
    return jsonify({"symbols": sorted([s.name for s in symbols])})

@app.route("/api/analyze", methods=["POST"])
def analyze():
    data         = request.json
    symbol       = data.get("symbol", "EURUSD")
    tf_str       = data.get("timeframe", "M5")
    days         = int(data.get("days", 10))
    min_body_pct = float(data.get("min_body_pct", 0))  # Filtro de corpo mínimo

    ok, err = init_mt5()
    if not ok:
        return jsonify({"error": f"MT5 init failed: {err}"}), 500

    tf = TIMEFRAME_MAP.get(tf_str)
    if tf is None:
        shutdown_mt5()
        return jsonify({"error": f"Timeframe inválido: {tf_str}"}), 400

    date_to   = datetime.now()
    date_from = date_to - timedelta(days=days)
    rates     = mt5.copy_rates_range(symbol, tf, date_from, date_to)
    shutdown_mt5()

    if rates is None or len(rates) == 0:
        return jsonify({"error": f"Sem dados para {symbol} no período solicitado"}), 404

    df_raw = pd.DataFrame(rates)
    df_raw["time"] = pd.to_datetime(df_raw["time"], unit="s")

    total_raw = len(df_raw)
    df = enrich_dataframe(df_raw, min_body_pct)
    filtered_out = total_raw - len(df)

    if len(df) == 0:
        return jsonify({"error": "Nenhuma vela passou pelo filtro de corpo mínimo. Reduza o valor."}), 400

    # ── Candles individuais ──
    candles = []
    green_count = red_count = 0
    for _, row in df.iterrows():
        rsi_val   = round(float(row["rsi"]), 1)
        rsi_label = "Sobrecomprado" if rsi_val >= 70 else "Sobrevendido" if rsi_val <= 30 else "Neutro"
        ema_trend = "Alta" if row["close"] > row["ema21"] else "Baixa"
        direction = row["direction"]
        candle = {
            "time":      row["time"].strftime("%Y-%m-%d %H:%M"),
            "date":      row["time"].strftime("%d/%m/%Y"),
            "hour":      row["hhmm"],
            "weekday":   DAYS_PT[int(row["weekday"])],
            "open":      round(float(row["open"]),  5),
            "high":      round(float(row["high"]),  5),
            "low":       round(float(row["low"]),   5),
            "close":     round(float(row["close"]), 5),
            "direction": direction,
            "body_size": round(float(row["body_size"]), 5),
            "body_pct":  round(float(row["body_pct"]),  1),
            "volume":    int(row["tick_volume"]),
            "vol_ratio": round(float(row["vol_ratio"]), 2),
            "rsi":       rsi_val,
            "rsi_label": rsi_label,
            "ema_trend": ema_trend,
        }
        candles.append(candle)
        if direction == "CALL": green_count += 1
        else:                   red_count   += 1

    total     = len(candles)
    green_pct = round(green_count / total * 100, 1) if total > 0 else 0
    red_pct   = round(red_count   / total * 100, 1) if total > 0 else 0

    # ── Análise por hora ──
    hourly = []
    for h in range(24):
        sub = df[df["hour_only"] == h]
        if len(sub) == 0: continue
        calls   = int((sub["direction"] == "CALL").sum())
        puts    = int((sub["direction"] == "PUT").sum())
        total_h = calls + puts
        bias    = "CALL" if calls >= puts else "PUT"
        hist_sc = round(max(calls, puts) / total_h * 100, 1) if total_h > 0 else 50
        rsi_avg = float(sub["rsi"].mean())
        vol_avg = float(sub["vol_ratio"].mean())
        ema_al  = float((sub["close"] > sub["ema21"]).mean()) if bias == "CALL" else float((sub["close"] < sub["ema21"]).mean())
        comp    = composite_score(hist_sc, rsi_avg, ema_al, vol_avg, bias)
        hourly.append({
            "hour":        f"{h:02d}:00",
            "calls":       calls, "puts": puts, "total": total_h,
            "call_pct":    round(calls / total_h * 100, 1) if total_h > 0 else 0,
            "put_pct":     round(puts  / total_h * 100, 1) if total_h > 0 else 0,
            "bias":        bias,
            "hist_score":  hist_sc,
            "rsi_avg":     round(rsi_avg, 1),
            "vol_avg":     round(vol_avg, 2),
            "ema_aligned": round(ema_al * 100, 1),
            "comp_score":  comp,
        })

    # ── Análise por dia da semana ──
    weekday_stats = []
    for wd in range(7):
        sub = df[df["weekday"] == wd]
        if len(sub) == 0: continue
        calls   = int((sub["direction"] == "CALL").sum())
        puts    = int((sub["direction"] == "PUT").sum())
        total_w = calls + puts
        bias    = "CALL" if calls >= puts else "PUT"
        hist_sc = round(max(calls, puts) / total_w * 100, 1) if total_w > 0 else 50
        rsi_avg = float(sub["rsi"].mean())
        vol_avg = float(sub["vol_ratio"].mean())
        ema_al  = float((sub["close"] > sub["ema21"]).mean()) if bias == "CALL" else float((sub["close"] < sub["ema21"]).mean())
        comp    = composite_score(hist_sc, rsi_avg, ema_al, vol_avg, bias)

        # Top 5 horários do dia
        hour_day = []
        for h in range(24):
            s2 = sub[sub["hour_only"] == h]
            if len(s2) < 2: continue
            c2 = int((s2["direction"] == "CALL").sum())
            p2 = int((s2["direction"] == "PUT").sum())
            t2 = c2 + p2
            b2 = "CALL" if c2 >= p2 else "PUT"
            r2 = float(s2["rsi"].mean())
            v2 = float(s2["vol_ratio"].mean())
            e2 = float((s2["close"] > s2["ema21"]).mean()) if b2=="CALL" else float((s2["close"] < s2["ema21"]).mean())
            sc2 = composite_score(round(max(c2,p2)/t2*100,1), r2, e2, v2, b2)
            hour_day.append({"hour": f"{h:02d}:00", "bias": b2, "score": sc2, "total": t2})
        hour_day.sort(key=lambda x: -x["score"])

        weekday_stats.append({
            "weekday":   wd,
            "name":      DAYS_PT[wd],
            "calls":     calls, "puts": puts, "total": total_w,
            "call_pct":  round(calls / total_w * 100, 1) if total_w > 0 else 0,
            "put_pct":   round(puts  / total_w * 100, 1) if total_w > 0 else 0,
            "bias":      bias,
            "hist_score": hist_sc,
            "rsi_avg":   round(rsi_avg, 1),
            "vol_avg":   round(vol_avg, 2),
            "comp_score": comp,
            "top_hours": hour_day[:5],
        })

    # ── Confluência hora × dia da semana ──
    confluence = []
    for wd in range(7):
        for h in range(24):
            sub = df[(df["weekday"] == wd) & (df["hour_only"] == h)]
            if len(sub) < 3: continue   # mínimo 3 amostras
            calls   = int((sub["direction"] == "CALL").sum())
            puts    = int((sub["direction"] == "PUT").sum())
            total_c = calls + puts
            bias    = "CALL" if calls >= puts else "PUT"
            hist_sc = round(max(calls, puts) / total_c * 100, 1)
            rsi_avg = float(sub["rsi"].mean())
            vol_avg = float(sub["vol_ratio"].mean())
            ema_al  = float((sub["close"] > sub["ema21"]).mean()) if bias=="CALL" else float((sub["close"] < sub["ema21"]).mean())
            comp    = composite_score(hist_sc, rsi_avg, ema_al, vol_avg, bias)

            # Consistência semanal para esse cruzamento
            hit_weeks   = int(sub.groupby("year_week").apply(lambda g: (g["direction"]==bias).any()).sum())
            total_weeks = int(sub["year_week"].nunique())
            consistency = round(hit_weeks / total_weeks * 100, 1) if total_weeks > 0 else 0

            confluence.append({
                "weekday":     wd,
                "day_name":    DAYS_PT[wd],
                "hour":        f"{h:02d}:00",
                "bias":        bias,
                "hist_score":  hist_sc,
                "comp_score":  comp,
                "consistency": consistency,
                "total":       total_c,
                "weeks":       total_weeks,
                "label":       f"{DAYS_PT[wd]} {h:02d}:00",
            })

    confluence.sort(key=lambda x: -x["comp_score"])

    # ── Análise de sequências ──
    directions  = df["direction"].tolist()
    seq_stats   = calc_sequence_stats(directions)

    # ── Consistência semanal (top horários) ──
    weekly_consistency = []
    for h_row in hourly:
        hour_str = h_row["hour"]
        bias     = h_row["bias"]
        cons, n_weeks = calc_weekly_consistency(df, hour_str, bias)
        weekly_consistency.append({
            "hour":        hour_str,
            "bias":        bias,
            "consistency": cons,
            "weeks":       n_weeks,
            "comp_score":  h_row["comp_score"],
        })
    weekly_consistency.sort(key=lambda x: -x["consistency"])

    # ── Sequências máximas ──
    max_green_seq = max_red_seq = cur_green = cur_red = 0
    for c in candles:
        if c["direction"] == "CALL":
            cur_green += 1; cur_red = 0
            max_green_seq = max(max_green_seq, cur_green)
        else:
            cur_red += 1; cur_green = 0
            max_red_seq = max(max_red_seq, cur_red)

    return jsonify({
        "symbol":              symbol,
        "timeframe":           tf_str,
        "days":                days,
        "min_body_pct":        min_body_pct,
        "date_from":           date_from.strftime("%d/%m/%Y %H:%M"),
        "date_to":             date_to.strftime("%d/%m/%Y %H:%M"),
        "total_candles":       total,
        "filtered_out":        filtered_out,
        "green_count":         green_count,
        "red_count":           red_count,
        "green_pct":           green_pct,
        "red_pct":             red_pct,
        "max_green_seq":       max_green_seq,
        "max_red_seq":         max_red_seq,
        "hourly_stats":        hourly,
        "weekday_stats":       weekday_stats,
        "confluence":          confluence[:50],
        "sequence_stats":      seq_stats,
        "weekly_consistency":  weekly_consistency,
        "candles":             candles,
    })

@app.route("/api/shutdown", methods=["POST"])
def shutdown():
    import threading
    def stop():
        import time, os, signal
        time.sleep(0.5)
        os.kill(os.getpid(), signal.SIGTERM)
    threading.Thread(target=stop, daemon=True).start()
    return jsonify({"ok": True})

@app.route("/api/filter-signals", methods=["POST"])
def filter_signals():
    data      = request.json
    raw_list  = data.get("signals", "")
    days      = int(data.get("days", 30))
    min_score = float(data.get("min_score", 60))
    min_body_pct = float(data.get("min_body_pct", 0))

    parsed_signals = []
    for line in raw_list.strip().splitlines():
        line = line.strip()
        if not line: continue
        parts = [p.strip() for p in line.split(",")]
        if len(parts) != 4: continue
        hour_str, symbol, direction, tf_str = parts
        direction = direction.upper(); tf_str = tf_str.upper()
        if direction not in ("CALL", "PUT"): continue
        if tf_str not in TIMEFRAME_MAP: continue
        parsed_signals.append({"hour": hour_str, "symbol": symbol.upper(), "direction": direction, "timeframe": tf_str})

    if not parsed_signals:
        return jsonify({"error": "Nenhum sinal válido encontrado na lista."}), 400

    ok, err = init_mt5()
    if not ok:
        return jsonify({"error": f"MT5 init failed: {err}"}), 500

    date_to   = datetime.now()
    date_from = date_to - timedelta(days=days)
    combos    = {}
    for s in parsed_signals:
        combos.setdefault((s["symbol"], s["timeframe"]), []).append(s)

    results = []
    for (symbol, tf_str), signals in combos.items():
        tf    = TIMEFRAME_MAP[tf_str]
        rates = mt5.copy_rates_range(symbol, tf, date_from, date_to)
        if rates is None or len(rates) == 0:
            for s in signals:
                results.append({**s, "error": "Sem dados históricos"})
            continue
        df = pd.DataFrame(rates)
        df["time"] = pd.to_datetime(df["time"], unit="s")
        df = enrich_dataframe(df, min_body_pct)

        for s in signals:
            target_hour = s["hour"]
            target_dir  = s["direction"]
            subset      = df[df["hhmm"] == target_hour]
            total_h     = len(subset)

            if total_h == 0:
                results.append({**s, "total": 0, "hits": 0, "comp_score": 0.0,
                                 "score": 0.0, "error": f"Nenhuma vela em {target_hour}"})
                continue

            hits      = int((subset["direction"] == target_dir).sum())
            hist_sc   = round(hits / total_h * 100, 1)
            rsi_avg   = float(subset["rsi"].mean())
            vol_avg   = float(subset["vol_ratio"].mean())
            ema_al    = float((subset["close"] > subset["ema21"]).mean()) if target_dir=="CALL" else float((subset["close"] < subset["ema21"]).mean())
            comp      = composite_score(hist_sc, rsi_avg, ema_al, vol_avg, target_dir)

            # Consistência semanal
            hit_weeks   = int(subset.groupby("year_week").apply(lambda g: (g["direction"]==target_dir).any()).sum())
            total_weeks = int(subset["year_week"].nunique())
            consistency = round(hit_weeks / total_weeks * 100, 1) if total_weeks > 0 else 0

            # Breakdown por dia da semana
            weekday_breakdown = []
            for wd in range(7):
                sw = subset[subset["weekday"] == wd]
                if len(sw) == 0: continue
                h_wd  = int((sw["direction"] == target_dir).sum())
                sc_wd = round(h_wd / len(sw) * 100, 1)
                weekday_breakdown.append({"name": DAYS_PT[wd], "hits": h_wd, "total": len(sw), "score": sc_wd})

            results.append({
                "hour":              target_hour,
                "symbol":            symbol,
                "direction":         target_dir,
                "timeframe":         tf_str,
                "total":             total_h,
                "hits":              hits,
                "misses":            total_h - hits,
                "hist_score":        hist_sc,
                "rsi_avg":           round(rsi_avg, 1),
                "vol_avg":           round(vol_avg, 2),
                "ema_aligned_pct":   round(ema_al * 100, 1),
                "comp_score":        comp,
                "score":             comp,
                "consistency":       consistency,
                "weeks":             total_weeks,
                "rating":            rating_from_score(comp),
                "approved":          comp >= min_score,
                "weekday_breakdown": weekday_breakdown,
            })

    shutdown_mt5()
    results.sort(key=lambda x: (-int(x.get("approved", False)), -x.get("comp_score", 0)))
    approved = [r for r in results if r.get("approved")]
    rejected = [r for r in results if not r.get("approved") and "error" not in r]
    no_data  = [r for r in results if "error" in r]
    return jsonify({"days": days, "min_score": min_score, "total_in": len(parsed_signals),
                    "approved": approved, "rejected": rejected, "no_data": no_data})


if __name__ == "__main__":
    import threading, webbrowser, sys, os
    PORT      = 5000
    is_frozen = getattr(sys, 'frozen', False)
    if is_frozen:
        app.template_folder = os.path.join(sys._MEIPASS, 'templates')

    def open_browser():
        import time; time.sleep(1.2)
        webbrowser.open(f"http://localhost:{PORT}")

    def run_tray():
        try:
            import pystray
            from PIL import Image, ImageDraw
            img  = Image.new("RGB", (64, 64), color="#050a0e")
            draw = ImageDraw.Draw(img)
            draw.ellipse([8, 8, 56, 56], fill="#00ffe0")
            draw.rectangle([28, 20, 36, 44], fill="#050a0e")
            draw.rectangle([20, 36, 44, 44], fill="#050a0e")
            def on_open(icon, item): webbrowser.open(f"http://localhost:{PORT}")
            def on_quit(icon, item):
                icon.stop()
                import signal; os.kill(os.getpid(), signal.SIGTERM)
            menu = pystray.Menu(
                pystray.MenuItem("Abrir no navegador", on_open, default=True),
                pystray.Menu.SEPARATOR,
                pystray.MenuItem("Encerrar", on_quit),
            )
            pystray.Icon("MT5 Signal Analyzer", img, "MT5 Signal Analyzer", menu).run()
        except Exception:
            pass

    threading.Thread(target=open_browser, daemon=True).start()
    threading.Thread(target=run_tray,    daemon=True).start()
    app.run(host="127.0.0.1", port=PORT, debug=False, use_reloader=False)
