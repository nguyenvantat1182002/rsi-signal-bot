import MetaTrader5 as mt5

from windows.models import TradingStrategyConfig
from typing import Union
from windows.models import Config
from PyQt5.QtCore import QThread, QReadWriteLock


class BaseThread(QThread):
    def __init__(self, rw_lock: QReadWriteLock):
        self.config = Config(rw_lock)
        self.order_type_mapping = {
            0: mt5.ORDER_TYPE_SELL_STOP,
            1: mt5.ORDER_TYPE_BUY_STOP
        }
        self.toggle_mapping = {
            0: 1,
            1: 0
        }
        super().__init__()

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
    
    def create_buy_sell_stop_order(self, symbol: str, order_type: int, volume: float, price: float, take_profit: float):
        request = {
            "action": mt5.TRADE_ACTION_PENDING,
            'symbol': symbol,
            "volume": volume,
            "type": order_type,
            "price": price,
            "tp": take_profit,
            'deviation': 30,
            "type_time": mt5.ORDER_TIME_GTC,
            "type_filling": mt5.ORDER_FILLING_IOC,
        }
        return mt5.order_send(request)
    
    def get_take_profit_price(self, signal: int, strategy_config: TradingStrategyConfig, entry: Union[int, float]) -> Union[int, float]:
        price_difference = strategy_config.position.price_difference * strategy_config.risk_reward

        take_profit = {
            0: entry + price_difference,
            1: entry - price_difference
        }
        
        return take_profit[signal]
