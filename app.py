import MetaTrader5 as mt5
import pandas as pd
import pandas_ta as ta
import detector
import threading
import time

from datetime import datetime, timedelta


def create_data_frame(symbol: str, timeframe: int) -> pd.DataFrame:
    rates = mt5.copy_rates_from_pos(symbol, timeframe, 0, 300)
    
    df = pd.DataFrame(rates)

    df['time'] = pd.to_datetime(rates['time'], unit='s')
    df['rsi'] = ta.rsi(df['close'], 14)
    df['atr'] = ta.atr(df['high'], df['low'], df['close'], 14)

    df.dropna(inplace=True)

    return df


risk_amount = 50
watchlist = {
    'BTCUSD': {
        'timeframe': mt5.TIMEFRAME_M5,
        'unit_factor': 0
    },
    'ETHUSD': {
        'timeframe': mt5.TIMEFRAME_M5,
        'unit_factor': 0
    },
    'XAUUSD': {
        'timeframe': mt5.TIMEFRAME_M5,
        'unit_factor': 100
    },
    'EURUSD': {
        'timeframe': mt5.TIMEFRAME_M5,
        'unit_factor': 100000
    },
    'GBPUSD': {
        'timeframe': mt5.TIMEFRAME_M5,
        'unit_factor': 100000
    },
    'NZDUSD': {
        'timeframe': mt5.TIMEFRAME_M5,
        'unit_factor': 100000
    },
    'AUDUSD': {
        'timeframe': mt5.TIMEFRAME_M5,
        'unit_factor': 100000
    },
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

                if price_current > take_profit:
                    watchlist[symbol]['position']['take_profit'] += price_difference

                    stop_loss = position.sl

                    match position.type:
                        case 0:
                            stop_loss =  stop_loss + price_difference
                        case 1:
                            stop_loss =  stop_loss - price_difference

                    request = {
                        'action': mt5.TRADE_ACTION_SLTP,
                        'position': position.ticket,
                        'sl': stop_loss,
                    }
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
                            print(symbol + '\n')

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

                            price_difference = abs(entry - stop_loss)
                            trade_volume = risk_amount / price_difference

                            if watchlist[symbol]['unit_factor'] != 0:
                                trade_volume = int(trade_volume)
                                trade_volume = trade_volume / watchlist[symbol]['unit_factor']

                            watchlist[symbol]['position']['price_difference'] = price_difference
                            watchlist[symbol]['position']['take_profit'] = entry + price_difference

                            trade_volume = round(trade_volume, 2)

                            request = {
                                'action': mt5.TRADE_ACTION_DEAL,
                                'symbol': symbol,
                                'deviation': 10,
                                'type': order_type,
                                'volume': trade_volume,
                                'price': entry,
                                'sl': stop_loss,
                            }
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
