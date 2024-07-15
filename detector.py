import pandas as pd

from typing import Optional


class RSIDivergenceDetector:
    def __init__(self, symbol: str, timeframe: int):
        self.symbol = symbol
        self.timeframe = timeframe

    def get_highest_pivot_bar(self, df: pd.DataFrame, pivot_bar: pd.Series, window_size: int = 2) -> pd.Series:
        left_bars = df[df['time'] < pivot_bar['time']].tail(window_size)
        right_bars = df[df['time'] > pivot_bar['time']].head(window_size)

        merged_df = pd.concat([left_bars, right_bars])
        highest_bar = merged_df.nlargest(1, 'high')
        highest_bar = highest_bar.iloc[-1]

        return pivot_bar if highest_bar['high'] < pivot_bar['high'] else highest_bar

    def get_lowest_pivot_bar(self, df: pd.DataFrame, pivot_bar: pd.Series, window_size: int = 2) -> pd.Series:
        left_bars = df[df['time'] < pivot_bar['time']].tail(window_size)
        right_bars = df[df['time'] > pivot_bar['time']].head(window_size)
        
        merged_df = pd.concat([left_bars, right_bars])
        lowest_bar = merged_df.nsmallest(1, 'low')
        lowest_bar = lowest_bar.iloc[-1]

        return pivot_bar if lowest_bar['low'] > pivot_bar['low'] else lowest_bar
    
    def is_bearish_divergence(self, df: pd.DataFrame, current_candle: pd.Series) -> Optional[pd.Series]:
        nearest_rsi_pivot_high = df[(df['rsi_pivot_high']) & (df['time'] < current_candle['time']) & (df['rsi'] > current_candle['rsi'])]
            
        if not nearest_rsi_pivot_high.empty:
            nearest_rsi_pivot_high = nearest_rsi_pivot_high.iloc[-1]
            
            if nearest_rsi_pivot_high['rsi'] > 70:
                current_candle = self.get_highest_pivot_bar(df, current_candle)
                nearest_pivot_high_candle = self.get_highest_pivot_bar(df, nearest_rsi_pivot_high)
                
                if current_candle['high'] > nearest_pivot_high_candle['high']:
                    return nearest_rsi_pivot_high
        
        return None

    def is_bullish_divergence(self, df: pd.DataFrame, current_candle: pd.Series) -> Optional[pd.Series]:
        nearest_rsi_pivot_low = df[(df['rsi_pivot_low']) & (df['time'] < current_candle['time']) & (df['rsi'] < current_candle['rsi'])]
        if not nearest_rsi_pivot_low.empty:
            nearest_rsi_pivot_low = nearest_rsi_pivot_low.iloc[-1]

            if nearest_rsi_pivot_low['rsi'] < 40:
                current_candle = self.get_lowest_pivot_bar(df, current_candle)
                nearest_pivot_low_candle = self.get_lowest_pivot_bar(df, nearest_rsi_pivot_low)

                if current_candle['low'] < nearest_pivot_low_candle['low']:
                    return nearest_rsi_pivot_low
            
        return None
    