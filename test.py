import pandas as pd
import pandas_ta as ta
import MetaTrader5 as mt5
import detector


def create_data_frame(symbol: str, timeframe: int) -> pd.DataFrame:
    rates = mt5.copy_rates_from_pos(symbol, timeframe, 0, 500)
    
    df = pd.DataFrame(rates)
    df['time'] = pd.to_datetime(df['time'], unit='s')
    df['rsi'] = ta.rsi(df['close'], 14)
    df['atr'] = ta.atr(df['high'], df['low'], df['close'], 14)

    df.dropna(inplace=True)

    return df


mt5.initialize()

df = create_data_frame('XAUUSDm', mt5.TIMEFRAME_M5)
result = detector.detect_divergence(df, 5)
if result is not None:
    print(result.divergence_type)
    print(result.rsi_point)
    print(result.price_point)
