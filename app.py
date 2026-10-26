import os, threading, time, requests, pandas as pd
from flask import Flask

app = Flask(__name__)

TELEGRAM_TOKEN = os.getenv("TELEGRAM_TOKEN")
TELEGRAM_CHAT_ID = os.getenv("TELEGRAM_CHAT_ID")
TWELVE_API_KEY = os.getenv("TWELVE_API_KEY")

sent_fvgs = set()

def send_telegram(msg):
    try:
        url = f"https://api.telegram.org/bot{TELEGRAM_TOKEN}/sendMessage"
        requests.post(url, data={"chat_id": TELEGRAM_CHAT_ID, "text": msg}, timeout=10)
    except Exception as e:
        print(e)

def ema(series, period):
    return series.ewm(span=period, adjust=False).mean()

def atr(df, period=14):
    hl = df['high'] - df['low']
    hc = (df['high'] - df['close'].shift()).abs()
    lc = (df['low'] - df['close'].shift()).abs()
    tr = pd.concat([hl, hc, lc], axis=1).max(axis=1)
    return tr.ewm(span=period, adjust=False).mean()

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
    df['EMA200'] = ema(df['close'], 200)
    df['ATR'] = atr(df, 14)
    return df

def fvg_loop():
    time.sleep(10)
    send_telegram("✅ Bot FVG XAU/USD redémarré - Fix doublon + expiry - Format Trade2Sync")
    while True:
        try:
            df = get_xau_h1()
            if df is None:
                time.sleep(60)
                continue
            
            last = df.iloc[-1]

            for i in range(len(df)-5, len(df)-1):
                # --- BULLISH FVG ---
                if df['low'].iloc[i-2] > df['high'].iloc[i]:
                    fvg_top = df['low'].iloc[i-2]
                    fvg_bottom = df['high'].iloc[i]
                    fvg_size = fvg_top - fvg_bottom
                    key = f"BULL-{fvg_bottom:.1f}-{fvg_top:.1f}"
                    
                    if key in sent_fvgs:
                        continue

                    if last['close'] > last['EMA200'] and fvg_size > last['ATR']*0.4:
                        entry = (fvg_top + fvg_bottom) / 2
                        # FIX: si prix trop loin de l'entrée, on ignore (signal expiré comme ton 4004 -> 4020)
                        if abs(last['close'] - entry) > last['ATR']*2.5:
                            continue
                        sl = fvg_bottom - last['ATR']*0.2
                        risk = entry - sl
                        tp1 = entry + risk*1.5
                        tp2 = entry + risk*3
                        msg = f"XAUUSD BUY\nENTRY {entry:.2f}\nSL {sl:.2f}\nTP1 {tp1:.2f}\nTP2 {tp2:.2f}\n\nID: {key}"
                        send_telegram(msg)
                        sent_fvgs.add(key)

                # --- BEARISH FVG ---
                if df['high'].iloc[i-2] < df['low'].iloc[i]:
                    fvg_bottom = df['high'].iloc[i-2]
                    fvg_top = df['low'].iloc[i]
                    fvg_size = fvg_top - fvg_bottom
                    key = f"BEAR-{fvg_bottom:.1f}-{fvg_top:.1f}"

                    if key in sent_fvgs:
                        continue

                    if last['close'] < last['EMA200'] and fvg_size > last['ATR']*0.4:
                        entry = (fvg_top + fvg_bottom) / 2
                        if abs(last['close'] - entry) > last['ATR']*2.5:
                            continue
                        sl = fvg_top + last['ATR']*0.2
                        risk = sl - entry
                        tp1 = entry - risk*1.5
                        tp2 = entry - risk*3
                        msg = f"XAUUSD SELL\nENTRY {entry:.2f}\nSL {sl:.2f}\nTP1 {tp1:.2f}\nTP2 {tp2:.2f}\n\nID: {key}"
                        send_telegram(msg)
                        sent_fvgs.add(key)

        except Exception as e:
            print(f"Erreur: {e}")
        time.sleep(60)

threading.Thread(target=fvg_loop, daemon=True).start()

@app.route('/')
def home():
    return "Bot FVG XAU Trade2Sync FIX OK", 200

if __name__ == "__main__":
    app.run(host='0.0.0.0', port=10000)
