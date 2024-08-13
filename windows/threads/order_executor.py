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
            '1M': mt5.TIMEFRAME_M1,
            '5M': mt5.TIMEFRAME_M5,
            '15M': mt5.TIMEFRAME_M15
        }

    def check_buy_sell_condition(self, symbol: int) -> int:
        rates = mt5.copy_rates_from_pos(symbol, mt5.TIMEFRAME_D1, 0, 2)

        df = pd.DataFrame(rates)
        df['time'] = pd.to_datetime(df['time'], unit='s')

        prev_candle = df.iloc[0]
        current_candle = df.iloc[-1]

        if current_candle['low'] < prev_candle['low'] and current_candle['close'] > prev_candle['low']:
            return 0
        elif current_candle['high'] > prev_candle['high'] and current_candle['close'] < prev_candle['high']:
            return 1
        
        return 2

    def create_data_frame(self, symbol: str, timeframe: int, count: int = 500) -> pd.DataFrame:
        rates = mt5.copy_rates_from_pos(symbol, timeframe, 0, count)
        
        df = pd.DataFrame(rates)
        df['time'] = pd.to_datetime(df['time'], unit='s')
        
        return df

    def get_take_profit_price(self, signal: int, position: Position, entry: Union[int, float]) -> Union[int, float]:
        take_profit = entry + position.price_difference

        if signal == 1:
            take_profit = entry - position.price_difference
        
        return take_profit
    
    def determine_order_parameters(self, df: pd.DataFrame, signal: int, info_tick: mt5.Tick):
        df['atr'] = ta.atr(df['high'], df['low'], df['close'], 14)

        atr = df['atr'].iloc[-2]

        order_type = mt5.ORDER_TYPE_BUY
        entry = info_tick.ask
        stop_loss = entry - atr * 5

        if signal == 1:
            order_type = mt5.ORDER_TYPE_SELL
            entry = info_tick.bid
            stop_loss = entry + atr * 5
            
        return order_type, entry, stop_loss

    def get_risk_amount(self, strategy_config: TradingStrategyConfig) -> Union[int, float]:
        risk_amount = strategy_config.risk_amount

        if strategy_config.auto:
            account = mt5.account_info()
            risk_amount = account.balance / strategy_config.max_total_orders

        return risk_amount

    def get_trade_volume(self,
                         strategy_config: TradingStrategyConfig,
                         entry: Union[int, float],
                         stop_loss: Union[int, float],
                         risk_amount: Union[int, float]) -> float:
        price_difference = abs(entry - stop_loss)
        trade_volume = risk_amount / price_difference

        if strategy_config.unit_factor != 0:
            trade_volume = int(trade_volume)
            trade_volume = trade_volume / strategy_config.unit_factor

        minimum_volume = 0.01
        trade_volume = round(trade_volume, 2) if trade_volume >= minimum_volume else minimum_volume

        return price_difference, trade_volume

    def run(self):
        while 1:
            config = self.config_manager.load_config()
            
            for key, value in config.items():
                strategy_config = TradingStrategyConfig(symbol=key, **value)
                
                if strategy_config.is_running and datetime.now() > strategy_config.next_search_signal_time:
                    timeframe = self.timeframe_mapping[strategy_config.timeframe]
                    df = self.create_data_frame(strategy_config.symbol, timeframe)

                    result = detector.detect_divergence(df)
                    if result:
                        divergence_time = result[-1][-1][0]

                        if divergence_time != strategy_config.divergence_time:
                            strategy_config.divergence_time = divergence_time

                            for item in result:
                                print(item)

                            condition = self.check_buy_sell_condition(strategy_config.symbol)
                            strategy_config.buy_only = condition == 0
                            strategy_config.sell_only = condition == 1

                            signal = result[0][-1]
                            if ((signal == 0 and strategy_config.buy_only) or (signal == 1 and strategy_config.sell_only)) and not mt5.positions_get(symbol=strategy_config.symbol):
                                info_tick = mt5.symbol_info_tick(strategy_config.symbol)

                                order_type, entry, stop_loss = self.determine_order_parameters(df, signal, info_tick)
                                risk_amount = self.get_risk_amount(strategy_config)
                                price_difference, trade_volume = self.get_trade_volume(strategy_config, entry, stop_loss, risk_amount)

                                strategy_config.position = Position()
                                strategy_config.position.price_difference = price_difference
                                strategy_config.position.take_profit = self.get_take_profit_price(signal, strategy_config.position, entry)
                                
                                request = {
                                    'action': mt5.TRADE_ACTION_DEAL,
                                    'symbol': strategy_config.symbol,
                                    'deviation': 10,
                                    'type': order_type,
                                    'volume': trade_volume,
                                    'price': entry,
                                    'sl': stop_loss,
                                }
                                print(request)
                                print()

                                result = mt5.order_send(request)
                                if not result.retcode == 10009:
                                    print(result)
                                    return

                    strategy_config.next_search_signal_time = datetime.now() + timedelta(minutes=timeframe)

                    config.update({strategy_config.symbol: strategy_config.model_dump(exclude='symbol')})

                    self.config_manager.update(config)

                QThread.msleep(1000)

            QThread.msleep(1000)