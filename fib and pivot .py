import MetaTrader5 as mt5
import pandas as pd
import time

# === Connect to MetaTrader 5 ===
symbol = "XAUUSD"
timeframe_small = mt5.TIMEFRAME_M5
timeframe_big = mt5.TIMEFRAME_M15

if not mt5.initialize():
    print("❌ MT5 initialization failed")
    quit()
print("✅ MT5 connected successfully")

# === Pivot Points Calculation ===
def calc_pivots(df):
    high = df['high'].iloc[-2]
    low = df['low'].iloc[-2]
    close = df['close'].iloc[-2]
    P = (high + low + close) / 3
    R1 = 2 * P - low
    S1 = 2 * P - high
    R2 = P + (high - low)
    S2 = P - (high - low)
    R3 = high + 2 * (P - low)
    S3 = low - 2 * (high - P)
    R4 = R3 + (R2 - R1)
    S4 = S3 - (S1 - S2)
    R5 = R4 + (R2 - R1)
    S5 = S4 - (S1 - S2)
    return {"P": P, "R3": R3, "R4": R4, "R5": R5, "S3": S3, "S4": S4, "S5": S5}

# === Fibonacci retracement levels ===
def calc_fib_levels(df):
    recent_high = df['high'].max()
    recent_low = df['low'].min()
    diff = recent_high - recent_low
    fib_levels = {
        "0%": recent_high,
        "23.6%": recent_high - 0.236 * diff,
        "38.2%": recent_high - 0.382 * diff,
        "50%": recent_high - 0.5 * diff,
        "61.8%": recent_high - 0.618 * diff,
        "78.6%": recent_high - 0.786 * diff,
        "100%": recent_low,
    }
    return fib_levels

# === Order placement function ===
def place_order(symbol, lot, order_type):
    symbol_info = mt5.symbol_info(symbol)
    if symbol_info is None:
        print("⚠️ Symbol not found:", symbol)
        return False
    if not symbol_info.visible:
        mt5.symbol_select(symbol, True)

    tick = mt5.symbol_info_tick(symbol)
    price = tick.ask if order_type == "buy" else tick.bid

    request = {
        "action": mt5.TRADE_ACTION_DEAL,
        "symbol": symbol,
        "volume": lot,
        "type": mt5.ORDER_TYPE_BUY if order_type == "buy" else mt5.ORDER_TYPE_SELL,
        "price": price,
        "deviation": 20,
        "magic": 2025,
        "comment": "FibPivotBot",
        "type_time": mt5.ORDER_TIME_GTC,
        "type_filling": mt5.ORDER_FILLING_IOC,
    }

    result = mt5.order_send(request)
    if result.retcode != mt5.TRADE_RETCODE_DONE:
        print(f"⚠️ Order failed: {result.retcode}")
    else:
        print(f"✅ {order_type.upper()} executed at {price}")
    return result

# === Main Bot ===
lot = float(input("Enter lot size (>=0.01): ") or 0.01)

print(f"\n🚀 Combined Strategy Bot (Pivot + Fibonacci)")
print(f"📊 Symbol: {symbol} | Timeframes: 5M + 15M")
print("💡 Conditions:")
print("   • Buys near S3–S5 or Fib 61.8% retracement in uptrend")
print("   • Sells near R3–R5 or Fib 61.8% retracement in downtrend\n")

last_action = None

while True:
    try:
        # === Get data ===
        df15 = pd.DataFrame(mt5.copy_rates_from_pos(symbol, timeframe_big, 0, 200))
        df5 = pd.DataFrame(mt5.copy_rates_from_pos(symbol, timeframe_small, 0, 200))
        if df15.empty or df5.empty:
            print("⚠️ No data received. Retrying...")
            time.sleep(5)
            continue

        df15.columns = ['time', 'open', 'high', 'low', 'close',
                        'tick_volume', 'spread', 'real_volume']
        df5.columns = ['time', 'open', 'high', 'low', 'close',
                       'tick_volume', 'spread', 'real_volume']

        piv = calc_pivots(df15)
        fib = calc_fib_levels(df5)

        price = df5['close'].iloc[-1]
        ema_fast = df5['close'].ewm(span=10).mean().iloc[-1]
        ema_slow = df15['close'].ewm(span=20).mean().iloc[-1]

        uptrend = ema_fast > ema_slow
        downtrend = ema_fast < ema_slow

        # === Buy setup ===
        if uptrend and (price <= fib["61.8%"] or price <= piv['S3']) and last_action != "buy":
            print(f"🟢 BUY Setup | Price: {price:.2f} | Fib 61.8: {fib['61.8%']:.2f} | S3: {piv['S3']:.2f}")
            place_order(symbol, lot, "buy")
            last_action = "buy"

        # === Sell setup ===
        elif downtrend and (price >= fib["61.8%"] or price >= piv['R3']) and last_action != "sell":
            print(f"🔴 SELL Setup | Price: {price:.2f} | Fib 61.8: {fib['61.8%']:.2f} | R3: {piv['R3']:.2f}")
            place_order(symbol, lot, "sell")
            last_action = "sell"

        time.sleep(60)  # one-minute interval

    except Exception as e:
        print("⚠️ Error:", e)
        time.sleep(10)
