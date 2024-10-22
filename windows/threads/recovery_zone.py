import MetaTrader5 as mt5

from windows.models import TradingStrategyConfig
from PyQt5.QtCore import QThread, QReadWriteLock
from .base import BaseThread


class RecoveryZoneThread(BaseThread):
    def __init__(self, rw_lock: QReadWriteLock):
        super().__init__(rw_lock)
    
    def run(self):
        while 1:
            config = self.config.get()
            for key, value in config.items():
                strategy_config = TradingStrategyConfig(symbol=key, **value)

                if strategy_config.is_running and strategy_config.position:
                    positions = mt5.positions_get(symbol=key)
                    if positions:
                        lastest_position = positions[-1]
                        
                        if not mt5.orders_get(symbol=key):
                            entry = strategy_config.position.stop_loss if lastest_position.type == positions[0].type else positions[0].price_open
                            take_profit = self.get_take_profit_price(self.toggle_mapping[lastest_position.type], strategy_config, entry)
                            trade_volume = lastest_position.volume * 2 if len(positions) < 2 else positions[-2].volume + positions[-1].volume
                            trade_volume = round(trade_volume, 2)

                            result = self.create_buy_sell_stop_order(
                                symbol=strategy_config.symbol,
                                order_type=self.order_type_mapping[lastest_position.type],
                                volume=trade_volume,
                                price=entry,
                                take_profit=take_profit
                            )
                            if not result.retcode == mt5.TRADE_RETCODE_DONE:
                                print(result)
                                print(__class__.__name__ + ':', 'Error')
                        else:
                            for item in positions[:-1]:
                                request = {
                                    'action': mt5.TRADE_ACTION_SLTP,
                                    'position': item.ticket,
                                }

                                if (item.type == 0 and lastest_position.type == 0) or (item.type == 1 and lastest_position.type == 1):
                                    request.update({'tp': lastest_position.tp})
                                else:
                                    request.update({'sl': lastest_position.tp})

                                mt5.order_send(request)
                    else:
                        pending_orders = mt5.orders_get(symbol=key)
                        for order in pending_orders:
                            request = {
                                'action': mt5.TRADE_ACTION_REMOVE,
                                'order': order.ticket
                            }
                            mt5.order_send(request)

                QThread.msleep(1000)

            QThread.msleep(3000)
