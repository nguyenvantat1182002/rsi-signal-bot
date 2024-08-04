import MetaTrader5 as mt5
import pandas as pd
import pandas_ta as ta
import detector
import threading
import time

from datetime import datetime, timedelta


def check_buy_sell_conditions(symbol: str) -> int:
    rates = mt5.copy_rates_from_pos(symbol, mt5.TIMEFRAME_H4, 0, 2)

    df = pd.DataFrame(rates)
    df['time'] = pd.to_datetime(df['time'], unit='s')

    prev_h4_candle = df.iloc[0]
    current_h4_candle = df.iloc[-1]

    if current_h4_candle['low'] < prev_h4_candle['low'] and current_h4_candle['close'] > prev_h4_candle['low']:
        return 0
    elif current_h4_candle['high'] > prev_h4_candle['high'] and current_h4_candle['close'] < prev_h4_candle['high']:
        return 1
    
    return 2


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
    'BTCUSD': {
        'timeframe': mt5.TIMEFRAME_M5,
        'unit_factor': 0,
    },
    'XAUUSD': {
        'timeframe': mt5.TIMEFRAME_M5,
        'unit_factor': 100,
    },
    'EURUSD': {
        'timeframe': mt5.TIMEFRAME_M5,
        'unit_factor': 100000,
    },
    'GBPUSD': {
        'timeframe': mt5.TIMEFRAME_M5,
        'unit_factor': 100000,
    },
    'AUDUSD': {
        'timeframe': mt5.TIMEFRAME_M5,
        'unit_factor': 100000,
    },
    'NZDUSD': {
        'timeframe': mt5.TIMEFRAME_M5,
        'unit_factor': 100000,
    },
}

for symbol in watchlist.keys():
    watchlist[symbol].update({
        'next_search_signal_time': datetime.now(),
        'divergence_time': None,
        'position': {
            'price_difference': -1,
            'take_profit': -1
        },
        'buy_only': True,
        'sell_only': True
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
                if not timeframe in [mt5.TIMEFRAME_M1, mt5.TIMEFRAME_M5, mt5.TIMEFRAME_M15]:
                    print('Chi ho tro 1m, 5m, 15m.')
                    return
                        
                condition = check_buy_sell_conditions(symbol)
                match condition:
                    case 0:
                        watchlist[symbol]['buy_only'] = True
                        watchlist[symbol]['sell_only'] = False
                    case 1:
                        watchlist[symbol]['buy_only'] = False
                        watchlist[symbol]['sell_only'] = True
                    case 2:
                        watchlist[symbol]['buy_only'] = False
                        watchlist[symbol]['sell_only'] = False

                if condition != 2:
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

                                buy_only = watchlist[symbol]['buy_only']
                                sell_only = watchlist[symbol]['sell_only']
                                
                                if (buy_only and order_type == mt5.ORDER_TYPE_BUY) or (sell_only and order_type == mt5.ORDER_TYPE_SELL):
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

                watchlist[symbol]['next_search_signal_time'] = datetime.now() + timedelta(minutes=timeframe)

        time.sleep(1)


if mt5.initialize():
    t = threading.Thread(target=profit_protection_thread, daemon=True)
    t.start()
    
    main()

mt5.shutdown()
