import os
import MetaTrader5 as mt5

from .edit_window import EditWindow
from typing import List
from windows.threads import OrderExecutorThread, RecoveryZoneThread
from windows.models import TradingStrategyConfig, Config
from PyQt5 import uic
from PyQt5.QtWidgets import QMainWindow, QTableWidgetItem, QPushButton
from PyQt5.QtCore import Qt, QFileSystemWatcher, QReadWriteLock
from PyQt5.QtGui import QCloseEvent


class MainWindow(QMainWindow):
    def __init__(self, version: int = 5):
        super().__init__()
        uic.loadUi(os.path.join(os.getcwd(), 'ui', 'MainWindow.ui'), self)

        self.version = version

        self.setWindowTitle(f'TRADER {self.version}')
        
        self.pushButton.clicked.connect(self.pushButton_clicked)
        self.pushButton_2.clicked.connect(self.pushButton_2_clicked)
        self.checkBox.stateChanged.connect(self.checkBox_stateChanged)
        
        self.rw_lock = QReadWriteLock()
        self.config = Config(self.rw_lock)
        self.edit_window = None

        file_watcher = QFileSystemWatcher(self)
        file_watcher.fileChanged.connect(self.on_file_changed)
        file_watcher.addPath(self.config.file_path)

        with self.config.load_and_update() as config:
            active_symbols = self.get_active_symbols(config)
            for symbol in active_symbols:
                if config[symbol]['is_running']:
                    config[symbol]['is_running'] = False

        self.load_table()

        self.order_executor = OrderExecutorThread(self.rw_lock)
        self.recovery_thread = RecoveryZoneThread(self.rw_lock)

        self.order_executor.start()
        self.recovery_thread.start()

    def get_active_symbols(self, config: dict) -> List[str]:
        return [symbol for symbol in config if config[symbol]['is_running']]

    def get_selected_symbol(self) -> str:
        row = self.tableWidget.currentRow()
        return self.tableWidget.item(row, 0).text()

    def load_table(self):
        config = self.config.get()

        button_actions = [[2, 'Bắt đầu', self.start_button_clicked],
                          [3, 'Chỉnh sửa', self.edit_button_clicked],
                          [4, 'Xóa', self.remove_button_clicked],
                          [5, 'Đóng tất cả lệnh', self.close_all_order]]
        
        while self.tableWidget.rowCount() > 0:
            self.tableWidget.removeRow(0)

        for key, value in config.items():
            row = self.tableWidget.rowCount()

            self.tableWidget.insertRow(row)
            self.tableWidget.setItem(row, 0, QTableWidgetItem(key))
            self.tableWidget.setItem(row, 1, QTableWidgetItem(value['timeframe']))

            for index, text, action in button_actions:
                button = QPushButton(text)
                button.setCursor(Qt.CursorShape.PointingHandCursor)
                button.clicked.connect(action)

                if index == 2 and value['is_running']:
                    button.setText('Dừng')
                elif index == 4 and value['is_running']:
                    button.setEnabled(False)

                self.tableWidget.setCellWidget(row, index, button)

    def start_button_clicked(self):
        symbol = self.get_selected_symbol()
        button: QPushButton = self.sender()
        
        with self.config.load_and_update() as config:
            match button.text():
                case 'Bắt đầu':
                    config[symbol]['is_running'] = True
                case 'Dừng':
                    config[symbol]['is_running'] = False

            active_symbols = self.get_active_symbols(config)
            
            match self.pushButton_2.text():
                case 'Bắt đầu':
                    if active_symbols:
                        self.pushButton_2.setText('Dừng')
                case 'Dừng':
                    if not active_symbols:
                        self.pushButton_2.setText('Bắt đầu')

    def edit_button_clicked(self):
        config = self.config.get()
        symbol = self.get_selected_symbol()
        strategy_config = TradingStrategyConfig(symbol=symbol, **config[symbol])
        
        self.edit_window = EditWindow(self.version, self.rw_lock, strategy_config)
        self.edit_window.show()

    def remove_button_clicked(self):
        with self.config.load_and_update() as config:
            symbol = self.get_selected_symbol()
            config.pop(symbol)
        
    def pushButton_clicked(self):
        self.edit_window = EditWindow(self.version, self.rw_lock)
        self.edit_window.show()

    def close_all_order(self):
        symbol = self.get_selected_symbol()
        positions = mt5.positions_get(symbol=symbol)

        if not positions:
            return
        
        position_type = {
            mt5.ORDER_TYPE_BUY: mt5.ORDER_TYPE_SELL,
            mt5.ORDER_TYPE_SELL: mt5.ORDER_TYPE_BUY
        }

        tick_info = mt5.symbol_info_tick(symbol)
        price = {
            mt5.ORDER_TYPE_BUY: tick_info.bid,
            mt5.ORDER_TYPE_SELL: tick_info.ask
        }

        for position in positions:
            request = {
                'action': mt5.TRADE_ACTION_DEAL,
                'position': position.ticket,
                'symbol': position.symbol,
                "volume": position.volume,
                'type': position_type[position.type],
                'price': price[position.type],
                'deviation': 30,
                "type_time": mt5.ORDER_TIME_GTC
            }

            mt5.order_send(request)

    def on_file_changed(self, _: str):
        self.load_table()

    def closeEvent(self, _: QCloseEvent):
        config = self.config.get()

        active_symbols = self.get_active_symbols(config)

        for symbol in active_symbols:
            config[symbol]['is_running'] = False

        if active_symbols:
            self.config.update(config)

    def pushButton_2_clicked(self):
        with self.config.load_and_update() as config:
            if not config:
                return
            
            start_stop_button_text = self.pushButton_2.text()
            
            for _, value in config.items():
                if start_stop_button_text == 'Bắt đầu' and not value['is_running']:
                    value['is_running'] = True
                elif start_stop_button_text == 'Dừng' and value['is_running']:
                    value['is_running'] = False
                            
            match start_stop_button_text:
                case 'Bắt đầu':
                    self.pushButton_2.setText('Dừng')
                case 'Dừng':
                    self.pushButton_2.setText('Bắt đầu')

    def checkBox_stateChanged(self):
        self.order_executor.multiple_pairs = self.checkBox.isChecked()
        