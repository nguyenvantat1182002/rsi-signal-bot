import MetaTrader5 as mt5

from windows.models import TradingStrategyConfig
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
    
    def get_take_profit_price(self, position_type: int, strategy_config: TradingStrategyConfig, entry: float) -> float:
        price_gap = strategy_config.position.price_gap * strategy_config.risk_reward

        take_profit = {
            0: entry + price_gap,
            1: entry - price_gap
        }
        
        return take_profit[position_type]
