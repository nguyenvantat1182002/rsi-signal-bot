import MetaTrader5 as mt5
import pandas as pd
import detector
import pandas_ta as ta

from typing import Union
from datetime import datetime, timedelta
from windows.models import TradingStrategyConfig, Position
from PyQt5.QtCore import QReadWriteLock, QThread
from .base import BaseThread


class OrderExecutorThread(BaseThread):
    def __init__(self, rw_lock: QReadWriteLock):
        super().__init__(rw_lock)

        self.timeframe_mapping = {
            '1m': mt5.TIMEFRAME_M1,
            '5m': mt5.TIMEFRAME_M5,
            '15m': mt5.TIMEFRAME_M15,
            '1h': mt5.TIMEFRAME_H1,
            '4h': mt5.TIMEFRAME_H4,
            '1d': mt5.TIMEFRAME_D1
        }

    def get_take_profit_price(self, signal: int, strategy_config: TradingStrategyConfig, entry: Union[int, float]) -> Union[int, float]:
        price_difference = strategy_config.position.price_difference

        if strategy_config.hedging_mode or strategy_config.use_risk_reward:
            price_difference = strategy_config.position.price_difference * strategy_config.risk_reward

        take_profit = {
            0: entry + price_difference,
            1: entry - price_difference
        }
        
        return take_profit[signal]

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

        if low_level_swept and is_bullish_reversal:
            return 0
        elif high_level_swept and is_bearish_reversal:
            return 1
        
        return 2

    def create_data_frame(self, symbol: str, timeframe: int, count: int = 500) -> pd.DataFrame:
        rates = mt5.copy_rates_from_pos(symbol, timeframe, 0, count)
        
        df = pd.DataFrame(rates)
        df['time'] = pd.to_datetime(df['time'], unit='s')

        df['rsi'] = ta.rsi(df['close'], 14)
        df['atr'] = ta.atr(df['high'], df['low'], df['close'], 14)

        df.dropna(inplace=True)
        
        return df

    def determine_order_parameters(self, df: pd.DataFrame, signal: int, info_tick: mt5.Tick, strategy_config: TradingStrategyConfig):
        atr = df['atr'].iloc[-2]
        order_type = mt5.ORDER_TYPE_BUY
        entry = info_tick.ask
        stop_loss = entry - atr * strategy_config.atr_multiplier

        if signal == 1:
            order_type = mt5.ORDER_TYPE_SELL
            entry = info_tick.bid
            stop_loss = entry + atr * strategy_config.atr_multiplier
            
        return order_type, entry, stop_loss

    def get_risk_amount(self, strategy_config: TradingStrategyConfig) -> Union[int, float]:
        risk_amount = strategy_config.risk_amount

        if strategy_config.auto:
            account = mt5.account_info()
            risk_amount = account.balance / strategy_config.max_total_orders

        return risk_amount
    
    def run(self):
        while 1:
            config = self.config.get()
            
            for key, value in config.items():
                strategy_config = TradingStrategyConfig(symbol=key, **value)
                
                if strategy_config.is_running and datetime.now() > strategy_config.next_search_signal_time:
                    timeframe = self.timeframe_mapping[strategy_config.timeframe]
                    df = self.create_data_frame(strategy_config.symbol, timeframe)

                    result = detector.detect_divergence(df, 5)
                    if result:
                        signal, _, rsi_lines = result
                        signal = signal[-1]
                        divergence_time = rsi_lines[-1][0]

                        if divergence_time != strategy_config.divergence_time:
                            strategy_config.divergence_time = divergence_time

                            for item in result:
                                print(item)
                            print(strategy_config.symbol)

                            condition = self.check_buy_sell_condition(strategy_config.symbol, self.timeframe_mapping[strategy_config.timeframe_filter])
                            buy_only = strategy_config.buy_only and condition == 0
                            sell_only = strategy_config.sell_only and condition == 1

                            if ((signal == 0 and buy_only) or (signal == 1 and sell_only)) and not mt5.positions_get(symbol=strategy_config.symbol):
                                info_tick = mt5.symbol_info_tick(strategy_config.symbol)

                                order_type, entry, stop_loss = self.determine_order_parameters(df, signal, info_tick, strategy_config)
                                risk_amount = self.get_risk_amount(strategy_config)
                                price_difference, trade_volume = self.get_trade_volume(strategy_config, entry, stop_loss, risk_amount)

                                strategy_config.position = Position()
                                strategy_config.position.price_difference = price_difference
                                strategy_config.position.stop_loss = stop_loss
                                strategy_config.position.take_profit = self.get_take_profit_price(signal, strategy_config, entry)

                                request = {
                                    'action': mt5.TRADE_ACTION_DEAL,
                                    'symbol': strategy_config.symbol,
                                    'deviation': 10,
                                    'type': order_type,
                                    'volume': trade_volume,
                                    'price': entry,
                                }

                                if not strategy_config.hedging_mode:
                                    if strategy_config.use_risk_reward:
                                        request.update({'tp': strategy_config.position.take_profit})

                                    request.update({'sl': stop_loss})
                                elif strategy_config.hedging_mode and strategy_config.use_default_volume:
                                    request.update({'volume': strategy_config.default_volume})

                                print(request)

                                result = mt5.order_send(request)
                                if not result.retcode == 10009:
                                    print(result)
                                    print(__class__.__name__ + ':', 'Stop')
                                    return
                                
                            print()

                    if not mt5.positions_get(symbol=strategy_config.symbol) and strategy_config.position:
                        strategy_config.position = None

                    strategy_config.next_search_signal_time = datetime.now() + timedelta(minutes=timeframe)

                    config.update({
                        strategy_config.symbol: strategy_config.model_dump(exclude='symbol')
                    })
                    self.config.update(config)

                QThread.msleep(1000)

            QThread.msleep(1000)
