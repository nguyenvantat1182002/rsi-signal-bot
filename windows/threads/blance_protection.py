import MetaTrader5 as mt5

from typing import Union
from PyQt5.QtCore import QThread
from windows.models import TradingStrategyConfig
from PyQt5.QtCore import QReadWriteLock
from .base import BaseThread


class BlanceProtectionThread(BaseThread):
    def __init__(self, rw_lock: QReadWriteLock):
        super().__init__(rw_lock)

        self.order_type_mapping = {
            0: mt5.ORDER_TYPE_SELL,
            1: mt5.ORDER_TYPE_BUY
        }
        self.toggle_mapping = {
            0: 1,
            1: 0
        }

    def get_take_profit_price(self, position: mt5.TradePosition, strategy_config: TradingStrategyConfig, entry: Union[int, float]):
        take_profit = {
            0: entry + (strategy_config.position.price_difference * strategy_config.risk_reward),
            1: entry - (strategy_config.position.price_difference * strategy_config.risk_reward)
        }

        return take_profit[self.toggle_mapping[position.type]]

    def get_stop_loss_price(self, position: mt5.TradePosition, strategy_config: TradingStrategyConfig, entry: Union[int, float]):
        stop_loss = {
            0: entry - strategy_config.position.price_difference,
            1: entry + strategy_config.position.price_difference
        }

        return stop_loss[self.toggle_mapping[position.type]]

    def close_all_positions(self, symbol: str):
        positions = mt5.positions_get(symbol=symbol)
        info_tick = mt5.symbol_info_tick(symbol)

        price = {
            0: info_tick.bid,
            1: info_tick.ask
        }

        for position in positions:
            request = dict(
                action=mt5.TRADE_ACTION_DEAL,
                type=self.order_type_mapping[position.type],
                price=price[position.type],
                symbol=position.symbol,
                volume=position.volume,
                position=position.ticket,
            )
            mt5.order_send(request)

    def get_entry(self, position: mt5.TradePosition, strategy_config: TradingStrategyConfig):
        info_tick = mt5.symbol_info_tick(strategy_config.symbol)
        entry = {
            0: info_tick.bid,
            1: info_tick.ask
        }

        return entry[position.type]

    def run(self):
        while 1:
            config = self.config.get()
            for key, value in config.items():
                positions = mt5.positions_get(symbol=key)
                positions = list(filter(lambda x: not x.sl and value['position'], positions if positions else ()))

                if positions:
                    position = positions[-1]
                    strategy_config = TradingStrategyConfig(symbol=key, **value)

                    if strategy_config.is_running:
                        stop_loss = strategy_config.position.stop_loss
                        take_profit = strategy_config.position.take_profit
                        price_current = position.price_current
                        
                        if (position.type == 0 and price_current > take_profit) or (position.type == 1 and price_current < take_profit):
                            # if len(mt5.positions_get(symbol=position.symbol)) > 1:
                            #     self.close_all_positions(position.symbol)
                            # else:
                            #     request = {
                            #         'action': mt5.TRADE_ACTION_SLTP,
                            #         'position': position.ticket,
                            #         'sl': stop_loss
                            #     }
                            #     mt5.order_send(request)

                            self.close_all_positions(position.symbol)
                        else:
                            if (position.type == 0 and price_current <= stop_loss) or (position.type == 1 and price_current >= stop_loss):
                                entry = self.get_entry(position, strategy_config)

                                strategy_config.position.take_profit = self.get_take_profit_price(position, strategy_config, entry)
                                strategy_config.position.stop_loss = self.get_stop_loss_price(position, strategy_config, entry)
    
                                request = {
                                    'action': mt5.TRADE_ACTION_DEAL,
                                    'symbol': strategy_config.symbol,
                                    'deviation': 10,
                                    'type': self.order_type_mapping[position.type],
                                    'volume': position.volume * 2,
                                    'price': entry,
                                }
                                result = mt5.order_send(request)

                                config.update({
                                    strategy_config.symbol: strategy_config.model_dump(exclude='symbol')
                                })
                                self.config.update(config)

                                if not result.retcode == 10009:
                                    print(result)
                                    print(__class__.__name__ + ':', 'Stop')
                                    return

                QThread.msleep(1000)
                
            QThread.msleep(1000)
