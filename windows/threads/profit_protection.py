import MetaTrader5 as mt5

from windows.models import TradingStrategyConfig
from PyQt5.QtCore import QReadWriteLock, QThread
from .base import BaseThread


class ProfitProtectionThread(BaseThread):
    def __init__(self, rw_lock: QReadWriteLock):
        super().__init__(rw_lock)

    def run(self):
        while 1:
            positions = mt5.positions_get()
            if positions:
                config = self.config_manager.load_config()

                for position in positions:
                    symbol = position.symbol

                    if symbol in config:
                        strategy_config = TradingStrategyConfig(symbol=symbol, **config[symbol])
                        price_difference = strategy_config.position.price_difference
                        take_profit = strategy_config.position.take_profit

                        price_current = position.price_current
                        request = {
                            'action': mt5.TRADE_ACTION_SLTP,
                            'position': position.ticket
                        }

                        match position.type:
                            case 0:
                                if price_current > take_profit:
                                    strategy_config.position.take_profit += price_difference
                                    stop_loss = position.sl + price_difference
                                    request.update({'sl': stop_loss})
                            case 1:
                                if take_profit > price_current:
                                    strategy_config.position.take_profit -= price_difference
                                    stop_loss =  position.sl - price_difference
                                    request.update({'sl': stop_loss})

                        if 'sl' in request:
                            mt5.order_send(request)

                            config.update({strategy_config.symbol: strategy_config.model_dump(exclude='symbol')})

                            self.config_manager.update(config)
                    
                    QThread.msleep(1000)

            QThread.msleep(1000)