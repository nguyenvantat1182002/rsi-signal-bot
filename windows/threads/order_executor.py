import MetaTrader5 as mt5
import pandas as pd
import detector
import pandas_ta as ta

from datetime import datetime, timedelta
from windows.models import TradingStrategyConfig, Position
from PyQt5.QtCore import QReadWriteLock, QThread
from .base import BaseThread


class OrderExecutorThread(BaseThread):
    def __init__(self, rw_lock: QReadWriteLock):
        super().__init__(rw_lock)

        self.multiple_pairs = True
        self.timeframe_mapping = {
            '1m': mt5.TIMEFRAME_M1,
            '5m': mt5.TIMEFRAME_M5,
            '15m': mt5.TIMEFRAME_M15,
            '1h': mt5.TIMEFRAME_H1,
            '4h': mt5.TIMEFRAME_H4,
            '1d': mt5.TIMEFRAME_D1
        }

    def check_buy_sell_condition(self, symbol: int, timeframe: int) -> int:
        rates = mt5.copy_rates_from_pos(symbol, timeframe, 0, 2)

        df = pd.DataFrame(rates)
        df['time'] = pd.to_datetime(df['time'], unit='s')

        prev_candle = df.iloc[0]
        current_candle = df.iloc[-1]

        low_level_swept = current_candle['low'] < prev_candle['low'] and current_candle['close'] > prev_candle['low']
        high_level_swept = current_candle['high'] > prev_candle['high'] and current_candle['close'] < prev_candle['high']

        is_bullish_reversal = (current_candle['close'] < prev_candle['close']) or (current_candle['close'] < prev_candle['open'])
        is_bearish_reversal = (current_candle['close'] > prev_candle['open']) or (current_candle['close'] > prev_candle['close'])

        result = 2

        if low_level_swept and is_bullish_reversal:
            result = 0
        elif high_level_swept and is_bearish_reversal:
            result = 1

        return result

    def create_data_frame(self, symbol: str, timeframe: int, count: int = 500, window_size: int = 5) -> pd.DataFrame:
        rates = mt5.copy_rates_from_pos(symbol, timeframe, 0, count)

        df = pd.DataFrame(rates)
        df['time'] = pd.to_datetime(df['time'], unit='s')

        df['rsi'] = ta.rsi(df['close'], 14)
        df['atr'] = ta.atr(df['high'], df['low'], df['close'], 14)

        df.dropna(inplace=True)

        df['rsi_pivot_high'] = df['rsi'] == df['rsi'].rolling(2 * window_size + 1, center=True).max()
        df['rsi_pivot_low'] = df['rsi'] == df['rsi'].rolling(2 * window_size + 1, center=True).min()
        df['pivot_high'] = df['high'] == df['high'].rolling(2 * window_size + 1, center=True).max()
        df['pivot_low'] = df['low'] == df['low'].rolling(2 * window_size + 1, center=True).min()
        
        return df
    
    def get_trade_volume(self,
                         strategy_config: TradingStrategyConfig,
                         entry: float,
                         stop_loss: float,
                         risk_amount: float) -> float:
        price_difference = abs(entry - stop_loss)
        trade_volume = risk_amount / price_difference

        if strategy_config.unit_factor != 0:
            trade_volume = int(trade_volume)
            trade_volume = trade_volume / strategy_config.unit_factor

        minimum_volume = 0.01
        trade_volume = round(trade_volume, 2) if trade_volume >= minimum_volume else minimum_volume

        return price_difference, trade_volume
    
    def determine_order_parameters(self, df: pd.DataFrame, strategy_config: TradingStrategyConfig, position_type: int):
        atr = df['atr'].iloc[-2]
        info_tick = mt5.symbol_info_tick(strategy_config.symbol)

        order_type = mt5.ORDER_TYPE_BUY
        entry = info_tick.ask
        stop_loss = entry - atr * strategy_config.atr_multiplier

        if position_type == 1:
            order_type = mt5.ORDER_TYPE_SELL
            entry = info_tick.bid
            stop_loss = entry + atr * strategy_config.atr_multiplier
            
        return order_type, entry, stop_loss

    def get_risk_amount(self, strategy_config: TradingStrategyConfig) -> float:
        risk_amount = strategy_config.risk_amount

        if strategy_config.risk_type == '%':
            account = mt5.account_info()
            risk_amount = (strategy_config.risk_amount / 100) * account.balance

        return risk_amount
    
    def run(self):
        while 1:
            config = self.config.get()
            
            for key, value in config.items():
                strategy_config = TradingStrategyConfig(symbol=key, **value)
                
                if strategy_config.is_running and datetime.now() > strategy_config.next_search_signal_time:
                    timeframe = self.timeframe_mapping[strategy_config.timeframe]

                    if not mt5.positions_get(symbol=strategy_config.symbol):
                        df = self.create_data_frame(strategy_config.symbol, timeframe, window_size=strategy_config.pivot_lookback)
                        
                        result = detector.detect_divergence(df, max_pivot_distance=strategy_config.pivot_distance)
                        if result is not None:
                            print(strategy_config.symbol, result.divergence_type)
                            print(result.rsi_point.start, result.rsi_point.end)
                            print(result.price_point.start, result.price_point.end)

                            buy_only = strategy_config.buy_only
                            sell_only = strategy_config.sell_only
                            
                            if strategy_config.use_filter:
                                for timeframe_filter in strategy_config.timeframe_filters[::-1]:
                                    condition = self.check_buy_sell_condition(
                                        symbol=strategy_config.symbol,
                                        timeframe=self.timeframe_mapping[timeframe_filter])
                                    print(timeframe_filter, condition)
                                    
                                    buy_only = strategy_config.buy_only and condition == 0
                                    sell_only = strategy_config.sell_only and condition == 1

                                    if condition != 2:
                                        break
                                
                                    QThread.msleep(300)

                            trading_allowed = False if not self.multiple_pairs and mt5.positions_total() > 0 else True

                            if trading_allowed and ((result.divergence_type == 0 and buy_only) or (result.divergence_type == 1 and sell_only)):
                                order_type, entry, stop_loss = self.determine_order_parameters(df, strategy_config, result.divergence_type)
                                risk_amount = self.get_risk_amount(strategy_config)
                                price_difference, trade_volume = self.get_trade_volume(strategy_config, entry, stop_loss, risk_amount)

                                strategy_config.position = Position()
                                strategy_config.position.price_difference = price_difference
                                strategy_config.position.stop_loss = stop_loss
                                strategy_config.position.take_profit = self.get_take_profit_price(result.divergence_type, strategy_config, entry)

                                request = {
                                    'symbol': strategy_config.symbol,
                                    'deviation': 30,
                                    'action': mt5.TRADE_ACTION_DEAL,
                                    'type': order_type,
                                    'volume': trade_volume,
                                    'price': entry,
                                    'tp': strategy_config.position.take_profit
                                }

                                if strategy_config.use_default_volume:
                                    request.update({'volume': strategy_config.default_volume})
                                    
                                result = mt5.order_send(request)
                                print(result)

                                if not result.retcode == mt5.TRADE_RETCODE_DONE:
                                    print(__class__.__name__ + ':', 'Stop')
                                    return
                                    
                            print()

                    if not mt5.positions_get(symbol=strategy_config.symbol) \
                            and not mt5.orders_get(symbol=strategy_config.symbol) \
                            and strategy_config.position:
                        strategy_config.position = None

                    strategy_config.next_search_signal_time = datetime.now() + timedelta(minutes=timeframe)

                    config.update({
                        strategy_config.symbol: strategy_config.model_dump(exclude='symbol')
                    })
                    self.config.update(config)

                QThread.msleep(1000)

            QThread.msleep(1000)
