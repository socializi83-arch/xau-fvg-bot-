import os, threading, time, requests, pandas as pd, pandas_ta as ta
from flask import Flask

app = Flask(__name__)

TELEGRAM_TOKEN = os.getenv("TELEGRAM_TOKEN")
TELEGRAM_CHAT_ID = os.getenv("TELEGRAM_CHAT_ID")
TWELVE_API_KEY = os.getenv("TWELVE_API_KEY")

sent_fvgs = set()

def send_telegram(msg):
    try:
        url = f"https://api.telegram.org/bot{TELEGRAM_TOKEN}/sendMessage"
        requests.post(url, data={"chat_id": TELEGRAM_CHAT_ID, "text": msg, "parse_mode": "Markdown"}, timeout=10)
    except Exception as e:
        print(e)

def get_xau_h1():
    url = f"https://api.twelvedata.com/time_series?symbol=XAU/USD&interval=1h&outputsize=100&apikey={TWELVE_API_KEY}"
    r = requests.get(url, timeout=15).json()
    if 'values' not in r:
        print(r)
        return None
    df = pd.DataFrame(r['values']).iloc[::-1]
    df['close'] = df['close'].astype(float)
    df['high'] = df['high'].astype(float)
    df['low'] = df['low'].astype(float)
    df['open'] = df['open'].astype(float)
    df['EMA200'] = ta.ema(df['close'], 200)
    df['ATR'] = ta.atr(df['high'], df['low'], df['close'], 14)
    return df

def fvg_loop():
    time.sleep(10)
    send_telegram("✅ *Bot FVG XAU/USD démarré*\nCheck toutes les 60 sec - UptimeRobot actif")
    while True:
        try:
            df = get_xau_h1()
            if df is None:
                time.sleep(60)
                continue
            for i in range(len(df)-4, len(df)-1):
                key = f"{i}-{df['close'].iloc[i]}"
                if key in sent_fvgs:
                    continue

                # BULLISH FVG
                if df['low'].iloc[i-2] > df['high'].iloc[i]:
                    fvg_top = df['low'].iloc[i-2]
                    fvg_bottom = df['high'].iloc[i]
                    fvg_size = fvg_top - fvg_bottom
                    last = df.iloc[-1]
                    if last['close'] > last['EMA200'] and fvg_size > last['ATR']*0.4:
                        entry = (fvg_top + fvg_bottom) / 2
                        sl = fvg_bottom - last['ATR']*0.2
                        risk = entry - sl
                        tp1 = entry + risk * 1.5
                        tp2 = entry + risk * 3
                        msg = f"🟢 *ACHAT XAU/USD - BULLISH FVG*\n\n*Entrée:* `{entry:.2f}`\n*SL:* `{sl:.2f}`\n*TP1:* `{tp1:.2f}` _(BE à TP1)_\n*TP2:* `{tp2:.2f}`\n\nZone {fvg_bottom:.2f}-{fvg_top:.2f}"
                        send_telegram(msg)
                        sent_fvgs.add(key)

                # BEARISH FVG
                if df['high'].iloc[i-2] < df['low'].iloc[i]:
                    fvg_bottom = df['high'].iloc[i-2]
                    fvg_top = df['low'].iloc[i]
                    fvg_size = fvg_top - fvg_bottom
                    last = df.iloc[-1]
                    if last['close'] < last['EMA200'] and fvg_size > last['ATR']*0.4:
                        entry = (fvg_top + fvg_bottom) / 2
                        sl = fvg_top + last['ATR']*0.2
                        risk = sl - entry
                        tp1 = entry - risk * 1.5
                        tp2 = entry - risk * 3
                        msg = f"🔴 *VENTE XAU/USD - BEARISH FVG*\n\n*Entrée:* `{entry:.2f}`\n*SL:* `{sl:.2f}`\n*TP1:* `{tp1:.2f}` _(BE à TP1)_\n*TP2:* `{tp2:.2f}`\n\nZone {fvg_bottom:.2f}-{fvg_top:.2f}"
                        send_telegram(msg)
                        sent_fvgs.add(key)
        except Exception as e:
            print(f"Erreur: {e}")
        time.sleep(60)

threading.Thread(target=fvg_loop, daemon=True).start()

@app.route('/')
def home():
    return "Bot FVG XAU OK", 200

if __name__ == "__main__":
    app.run(host='0.0.0.0', port=10000)
