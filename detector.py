import pandas as pd

from dataclasses import dataclass
from typing import Optional


@dataclass
class DivergencePoint:
    start: tuple
    end: tuple


@dataclass
class DivergenceSignal:
    divergence_type: int
    rsi_point: DivergencePoint
    price_point: DivergencePoint


def is_highest_pivot(df: pd.DataFrame, pivot_1: pd.Series, pivot_2: pd.Series) -> bool:
    tmp = df[(df['time'] >= pivot_1['time']) & (df['time'] <= pivot_2['time'])]
    highest_candle = tmp.nlargest(1, 'high').iloc[-1]
    return highest_candle['time'] == pivot_2['time']


def is_lowest_pivot(df: pd.DataFrame, pivot_1: pd.Series, pivot_2: pd.Series) -> bool:
    tmp = df[(df['time'] >= pivot_1['time']) & (df['time'] <= pivot_2['time'])]
    lowest_candle = tmp.nsmallest(1, 'low').iloc[-1]
    return lowest_candle['time'] == pivot_2['time']


def get_highest_pivot_bar(df: pd.DataFrame, pivot_candle: pd.Series, window_size: int = 5) -> pd.Series:
    left_bars = df[df['time'] < pivot_candle['time']].tail(window_size)
    right_bars = df[df['time'] > pivot_candle['time']].head(window_size)

    merged_df = pd.concat([left_bars, right_bars])
    # highest_bar = merged_df.nlargest(1, 'high')
    # highest_bar = highest_bar.iloc[-1]

    # return pivot_candle if highest_bar['high'] < pivot_candle['high'] else highest_bar

    highest_bar = merged_df[merged_df['pivot_high']]
    if highest_bar.empty:
        return pivot_candle if pivot_candle['pivot_high'] else None
    
    highest_bar = highest_bar.iloc[-1]

    return highest_bar


def get_lowest_pivot_bar(df: pd.DataFrame, pivot_candle: pd.Series, window_size: int = 5) -> pd.Series:
    left_bars = df[df['time'] < pivot_candle['time']].tail(window_size)
    right_bars = df[df['time'] > pivot_candle['time']].head(window_size)
    
    merged_df = pd.concat([left_bars, right_bars])
    # lowest_bar = merged_df.nsmallest(1, 'low')
    # lowest_bar = lowest_bar.iloc[-1]

    # return pivot_candle if lowest_bar['low'] > pivot_candle['low'] else lowest_bar

    lowest_bar = merged_df[merged_df['pivot_low']]
    if lowest_bar.empty:
        return pivot_candle if pivot_candle['pivot_low'] else None
        
    lowest_bar = lowest_bar.iloc[-1]

    return lowest_bar


def is_bearish_divergence(df: pd.DataFrame, current_pivot_high: pd.Series) -> Optional[pd.Series]:
    nearest_rsi_pivot_high = df[(df['rsi_pivot_high']) & (df['time'] < current_pivot_high['time']) & (df['rsi'] > current_pivot_high['rsi']) & (df['rsi'] > 70)]
        
    if not nearest_rsi_pivot_high.empty:
        nearest_rsi_pivot_high = nearest_rsi_pivot_high.iloc[-1]

        if is_highest_pivot(df, nearest_rsi_pivot_high, current_pivot_high):
        
            current_pivot_high_candle = get_highest_pivot_bar(df, current_pivot_high)
            nearest_pivot_high_candle = get_highest_pivot_bar(df, nearest_rsi_pivot_high)

            if current_pivot_high_candle is not None and nearest_pivot_high_candle is not None:
                if current_pivot_high_candle['high'] > nearest_pivot_high_candle['high']:
                    return nearest_rsi_pivot_high
    
    return None


def is_bullish_divergence(df: pd.DataFrame, current_pivot_low: pd.Series) -> Optional[pd.Series]:
    nearest_rsi_pivot_low = df[(df['rsi_pivot_low']) & (df['time'] < current_pivot_low['time']) & (df['rsi'] < current_pivot_low['rsi']) & (df['rsi'] < 30)]
    if not nearest_rsi_pivot_low.empty:
        nearest_rsi_pivot_low = nearest_rsi_pivot_low.iloc[-1]


        if is_lowest_pivot(df, nearest_rsi_pivot_low, current_pivot_low):

            current_pivot_low_candle = get_lowest_pivot_bar(df, current_pivot_low)
            nearest_pivot_low_candle = get_lowest_pivot_bar(df, nearest_rsi_pivot_low)

            if current_pivot_low_candle is not None and nearest_pivot_low_candle is not None:
                if current_pivot_low['low'] < nearest_pivot_low_candle['low']:
                    return nearest_rsi_pivot_low
        
    return None


def detect_divergence(df: pd.DataFrame, max_pivot_distance: int = 9) -> Optional[DivergenceSignal]:
    df = df.copy()
    df = df.tail(150)
    
    prev_candle = df.iloc[-2]

    current_rsi_pivot_low = df[df['rsi_pivot_low']].iloc[-1]
    current_pivot_low = df[df['pivot_low']].iloc[-1]
    distance_to_pivot_low = len(df) - df.index.get_loc(current_pivot_low.name) - 1
    bullish_divergence_point = is_bullish_divergence(df, current_rsi_pivot_low)
    if bullish_divergence_point is not None \
            and distance_to_pivot_low <= max_pivot_distance \
            and prev_candle['close'] > current_pivot_low['high']:
        current_pivot_low_candle = get_lowest_pivot_bar(df, current_rsi_pivot_low)
        nearest_pivot_low_candle = get_lowest_pivot_bar(df, bullish_divergence_point)

        return DivergenceSignal(
            divergence_type=0,
            rsi_point=DivergencePoint(
                start=(bullish_divergence_point['time'], bullish_divergence_point['rsi']),
                end=(current_rsi_pivot_low['time'], current_rsi_pivot_low['rsi'])
            ),
            price_point=DivergencePoint(
                start=(nearest_pivot_low_candle['time'], nearest_pivot_low_candle['low']),
                end=(current_pivot_low_candle['time'], current_pivot_low_candle['low'])
            )
        )
    
    current_rsi_pivot_high = df[df['rsi_pivot_high']].iloc[-1]
    current_pivot_high = df[df['pivot_high']].iloc[-1]
    distance_to_pivot_high = len(df) - df.index.get_loc(current_pivot_high.name) - 1
    bearish_divergence_point = is_bearish_divergence(df, current_rsi_pivot_high)
    if bearish_divergence_point is not None \
            and distance_to_pivot_high <= max_pivot_distance \
            and prev_candle['close'] < current_pivot_high['low']:
        current_pivot_high_candle = get_highest_pivot_bar(df, current_rsi_pivot_high)
        nearest_pivot_high_candle = get_highest_pivot_bar(df, bearish_divergence_point)

        return DivergenceSignal(
            divergence_type=1,
            rsi_point=DivergencePoint(
                start=(bearish_divergence_point['time'], bearish_divergence_point['rsi']),
                end=(current_rsi_pivot_high['time'], current_rsi_pivot_high['rsi'])
            ),
            price_point=DivergencePoint(
                start=(nearest_pivot_high_candle['time'], nearest_pivot_high_candle['high']),
                end=(current_pivot_high_candle['time'], current_pivot_high_candle['high'])
            )
        )

    return None
