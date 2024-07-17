import pandas as pd

from typing import Optional


def get_highest_pivot_bar(df: pd.DataFrame, pivot_candle: pd.Series, window_size: int = 2) -> pd.Series:
    left_bars = df[df['time'] < pivot_candle['time']].tail(window_size)
    right_bars = df[df['time'] > pivot_candle['time']].head(window_size)

    merged_df = pd.concat([left_bars, right_bars])
    highest_bar = merged_df.nlargest(1, 'high')
    highest_bar = highest_bar.iloc[-1]

    return pivot_candle if highest_bar['high'] < pivot_candle['high'] else highest_bar


def get_lowest_pivot_bar(df: pd.DataFrame, pivot_candle: pd.Series, window_size: int = 2) -> pd.Series:
    left_bars = df[df['time'] < pivot_candle['time']].tail(window_size)
    right_bars = df[df['time'] > pivot_candle['time']].head(window_size)
    
    merged_df = pd.concat([left_bars, right_bars])
    lowest_bar = merged_df.nsmallest(1, 'low')
    lowest_bar = lowest_bar.iloc[-1]

    return pivot_candle if lowest_bar['low'] > pivot_candle['low'] else lowest_bar


def is_bearish_divergence(df: pd.DataFrame, current_pivot_high: pd.Series) -> Optional[pd.Series]:
    nearest_rsi_pivot_high = df[(df['rsi_pivot_high']) & (df['time'] < current_pivot_high['time']) & (df['rsi'] > current_pivot_high['rsi'])]
        
    if not nearest_rsi_pivot_high.empty:
        nearest_rsi_pivot_high = nearest_rsi_pivot_high.iloc[-1]
        
        if nearest_rsi_pivot_high['rsi'] > 70:
            current_pivot_high = get_highest_pivot_bar(df, current_pivot_high)
            nearest_pivot_high_candle = get_highest_pivot_bar(df, nearest_rsi_pivot_high)
            
            if current_pivot_high['high'] > nearest_pivot_high_candle['high']:
                return nearest_rsi_pivot_high
    
    return None


def is_bullish_divergence(df: pd.DataFrame, current_pivot_low: pd.Series) -> Optional[pd.Series]:
    nearest_rsi_pivot_low = df[(df['rsi_pivot_low']) & (df['time'] < current_pivot_low['time']) & (df['rsi'] < current_pivot_low['rsi'])]
    if not nearest_rsi_pivot_low.empty:
        nearest_rsi_pivot_low = nearest_rsi_pivot_low.iloc[-1]

        if nearest_rsi_pivot_low['rsi'] < 40:
            current_pivot_low = get_lowest_pivot_bar(df, current_pivot_low)
            nearest_pivot_low_candle = get_lowest_pivot_bar(df, nearest_rsi_pivot_low)

            if current_pivot_low['low'] < nearest_pivot_low_candle['low']:
                return nearest_rsi_pivot_low
        
    return None


def detect_divergence(df: pd.DataFrame, window_size: int = 3) -> list:
    df = df.copy()

    df['rsi_pivot_high'] = df['rsi'] == df['rsi'].rolling(2 * window_size + 1, center=True).max()
    df['rsi_pivot_low'] = df['rsi'] == df['rsi'].rolling(2 * window_size + 1, center=True).min()

    current_pivot_low = df[df['rsi_pivot_low']].iloc[-1]
    bullish_divergence_point = is_bullish_divergence(df, current_pivot_low)
    if bullish_divergence_point is not None:
        tmp = get_lowest_pivot_bar(df, current_pivot_low)
        nearest_pivot_low_candle = get_lowest_pivot_bar(df, bullish_divergence_point)

        return [
            [0],
            [(bullish_divergence_point['time'], bullish_divergence_point['rsi']), (current_pivot_low['time'], current_pivot_low['rsi'])],
            [(nearest_pivot_low_candle['time'], nearest_pivot_low_candle['low']), (tmp['time'], tmp['low'])]
        ]
    
    current_pivot_high = df[df['rsi_pivot_high']].iloc[-1]
    bearish_divergence_point = is_bearish_divergence(df, current_pivot_high)
    if bearish_divergence_point is not None:
        tmp = get_highest_pivot_bar(df, current_pivot_high)
        nearest_pivot_high_candle = get_highest_pivot_bar(df, bearish_divergence_point)

        return [
            [1],
            [(bearish_divergence_point['time'], bearish_divergence_point['rsi']), (current_pivot_high['time'], current_pivot_high['rsi'])],
            [(nearest_pivot_high_candle['time'], nearest_pivot_high_candle['high']), (tmp['time'], tmp['high'])]
        ]

    return []
