import MetaTrader5 as mt5
import pandas as pd
import detector
import pandas_ta as ta
import asyncio

from typing import List
from telethon.sync import TelegramClient
from telethon.sessions import StringSession
from telethon.tl.custom import Dialog
from typing import Union
from datetime import datetime, timedelta
from windows.models import TradingStrategyConfig, Position
from PyQt5.QtCore import QReadWriteLock, QThread
from .base import BaseThread


API_ID = 11501122
API_HASH = 'd29b3333c768f6ef6a8167bebc67b2db'


class OrderExecutorThread(BaseThread):
    def __init__(self, rw_lock: QReadWriteLock):
        super().__init__(rw_lock)

        self.timeframe_mapping = {
            '1m': mt5.TIMEFRAME_M1,
            '5m': mt5.TIMEFRAME_M5,
            '15m': mt5.TIMEFRAME_M15,
            '4h': mt5.TIMEFRAME_H4,
            '1d': mt5.TIMEFRAME_D1
        }
        self.order_type_mapping = {
            mt5.ORDER_TYPE_BUY: 'BUY',
            mt5.ORDER_TYPE_SELL: 'SELL'
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

        df.set_index(df['time'], inplace=True)
        df.dropna(inplace=True)
        
        return df

    def get_take_profit_price(self, signal: int, position: Position, entry: Union[int, float]) -> Union[int, float]:
        take_profit = entry + position.price_difference

        if signal == 1:
            take_profit = entry - position.price_difference
        
        return take_profit
    
    def determine_order_parameters(self, df: pd.DataFrame, signal: int, info_tick: mt5.Tick):
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

                                result = mt5.order_send(request)
                                
                                if strategy_config.noti_telegram:
                                    with open('me.session', encoding='utf-8') as file:
                                        session = file.read()

                                    new_loop = asyncio.new_event_loop()
                                    asyncio.set_event_loop(new_loop)

                                    with TelegramClient(StringSession(session), API_ID, API_HASH, loop=new_loop) as client:
                                        dialogs: List[Dialog] = client.get_dialogs()
                                        dialog = [dialog for dialog in dialogs if dialog.name == 'TRADER 2']
                                        dialog: Dialog = dialog[0]
                                        entity = dialog.entity
            
                                        position = mt5.positions_get(symbol=strategy_config.symbol)[0]
                                        message = f'{strategy_config.symbol} {self.order_type_mapping[order_type]}\nSL: {position.sl}'
                                        client.send_message(entity, message)

                                if not result.retcode == 10009:
                                    print(result)
                                    print('Stop')
                                    return

                            print()

                    strategy_config.next_search_signal_time = datetime.now() + timedelta(minutes=timeframe)

                    config.update({strategy_config.symbol: strategy_config.model_dump(exclude='symbol')})

                    self.config_manager.update(config)

                QThread.msleep(1000)

            QThread.msleep(1000)
