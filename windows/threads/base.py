from windows.models import TradingStrategyConfig
from typing import Union
from windows.models import Config
from PyQt5.QtCore import QThread, QReadWriteLock


class BaseThread(QThread):
    def __init__(self, rw_lock: QReadWriteLock):
        self.config = Config(rw_lock)
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
    