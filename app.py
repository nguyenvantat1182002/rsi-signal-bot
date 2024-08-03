import MetaTrader5 as mt5
import pandas as pd
import pandas_ta as ta
import detector
import threading
import time

from datetime import datetime, timedelta


def create_data_frame(symbol: str, timeframe: int) -> pd.DataFrame:
    rates = mt5.copy_rates_from_pos(symbol, timeframe, 0, 500)
    
    df = pd.DataFrame(rates)

    df['time'] = pd.to_datetime(df['time'], unit='s')
    df['rsi'] = ta.rsi(df['close'], 14)
    df['atr'] = ta.atr(df['high'], df['low'], df['close'], 14)

    df.dropna(inplace=True)

    return df


# risk_amount = 10
watchlist = {
    'BTCUSDm': {
        'timeframe': mt5.TIMEFRAME_M5,
        'unit_factor': 0
    }
}

for symbol in watchlist.keys():
    watchlist[symbol].update({
        'next_search_signal_time': datetime.now(),
        'divergence_time': None,
        'position': {
            'price_difference': -1,
            'take_profit': -1
        }
    })


def profit_protection_thread():
    while True:
        positions = mt5.positions_get()
        if positions:
            for position in positions:
                symbol = position.symbol
                price_current = position.price_current

                price_difference = watchlist[symbol]['position']['price_difference']
                take_profit = watchlist[symbol]['position']['take_profit']
                request = {
                    'action': mt5.TRADE_ACTION_SLTP,
                    'position': position.ticket
                }

                match position.type:
                    case 0:
                        if price_current > take_profit:
                            watchlist[symbol]['position']['take_profit'] += price_difference
                            stop_loss = position.sl + price_difference
                            request.update({'sl': stop_loss})
                    case 1:
                        if take_profit > price_current:
                            watchlist[symbol]['position']['take_profit'] -= price_difference
                            stop_loss =  position.sl - price_difference
                            request.update({'sl': stop_loss})

                if 'sl' in request:
                    mt5.order_send(request)

        time.sleep(1)
    

def main():
    while True:
        for symbol in watchlist:
            next_search_signal_time = watchlist[symbol]['next_search_signal_time']
            if datetime.now() > next_search_signal_time:
                timeframe = watchlist[symbol]['timeframe']
                time_duration = None
                match timeframe:
                    case mt5.TIMEFRAME_M1 | mt5.TIMEFRAME_M5 | mt5.TIMEFRAME_M15:
                        time_duration = timedelta(minutes=timeframe)
                    case mt5.TIMEFRAME_H1:
                        time_duration = timedelta(minutes=60)
                    case mt5.TIMEFRAME_H4:
                        time_duration = timedelta(minutes=240)
                    case _:
                        print('Chi ho tro 1m, 5m, 15m, 1h, 4h.')
                        return
                    
                df = create_data_frame(symbol, timeframe)

                result = detector.detect_divergence(df)
                if result:
                    divergence_time = result[-1][-1][0]

                    if watchlist[symbol]['divergence_time'] is None:
                        watchlist[symbol]['divergence_time'] = divergence_time

                    if divergence_time != watchlist[symbol]['divergence_time']:
                        watchlist[symbol]['divergence_time'] = divergence_time

                        if not mt5.positions_get(symbol=symbol):
                            
                            for item in result:
                                print(item)

                            info_tick = mt5.symbol_info_tick(symbol)
                            order_type = None
                            entry = 0
                            stop_loss = 0
                            atr = df['atr'].iloc[-2]

                            signal = result[0][-1]
                            match signal:
                                case 0:
                                    order_type = mt5.ORDER_TYPE_BUY
                                    entry = info_tick.ask
                                    stop_loss = entry - atr * 5
                                case 1:
                                    order_type = mt5.ORDER_TYPE_SELL
                                    entry = info_tick.bid
                                    stop_loss = entry + atr * 5

                            account = mt5.account_info()
                            balance = account.balance
                            risk_amount = balance / 10
                            
                            price_difference = abs(entry - stop_loss)
                            trade_volume = risk_amount / price_difference

                            if watchlist[symbol]['unit_factor'] != 0:
                                trade_volume = int(trade_volume)
                                trade_volume = trade_volume / watchlist[symbol]['unit_factor']

                            watchlist[symbol]['position']['price_difference'] = price_difference

                            match signal:
                                case 0:
                                    watchlist[symbol]['position']['take_profit'] = entry + price_difference
                                case 1:
                                    watchlist[symbol]['position']['take_profit'] = entry - price_difference

                            minimum_volume = 0.01
                            trade_volume = round(trade_volume, 2) if trade_volume >= minimum_volume else minimum_volume

                            request = {
                                'action': mt5.TRADE_ACTION_DEAL,
                                'symbol': symbol,
                                'deviation': 10,
                                'type': order_type,
                                'volume': trade_volume,
                                'price': entry,
                                'sl': stop_loss,
                            }
                            print(symbol, trade_volume)
                            print(request)
                            print()

                            result = mt5.order_send(request)
                            if not result.retcode == 10009:
                                print(result)
                                return
        
                watchlist[symbol]['next_search_signal_time'] = datetime.now() + time_duration

        time.sleep(1)


if mt5.initialize():
    t = threading.Thread(target=profit_protection_thread, daemon=True)
    t.start()
    
    main()

mt5.shutdown()
