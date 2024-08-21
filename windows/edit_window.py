import os
import MetaTrader5 as mt5

from pydantic import ValidationError
from typing import Optional
from windows.models import TradingStrategyConfig, JsonFileManager
from functools import lru_cache
from PyQt5 import uic
from PyQt5.QtWidgets import QMainWindow, QCompleter, QMessageBox
from PyQt5.QtGui import QStandardItem, QStandardItemModel
from PyQt5.QtCore import QReadWriteLock


@lru_cache(maxsize=8)
def get_symbols():
    symbols = mt5.symbols_get()
    return [item.name for item in symbols]


class EditWindow(QMainWindow):
    def __init__(self, rw_lock: QReadWriteLock, strategy_config: Optional[TradingStrategyConfig] = None):
        super().__init__()
        uic.loadUi(os.path.join(os.getcwd(), 'ui', 'EditWindow.ui'), self)

        self.rw_lock = rw_lock
        self.strategy_config = strategy_config
        
        self.lineEdit.textChanged.connect(self.lineEdit_textChanged)
        self.checkBox.stateChanged.connect(self.checkBox_stateChanged)
        self.pushButton.clicked.connect(self.pushButton_clicked)

        self.symbols_model  = QStandardItemModel()
        self.lineEdit.setCompleter(QCompleter(self.symbols_model, self))

        symbols = get_symbols()
        for symbol in symbols:
            self.symbols_model.appendRow(QStandardItem(symbol))

        if self.strategy_config is not None:
            self.setWindowTitle(f'{self.strategy_config.symbol} - EDIT')
            self.lineEdit.setText(self.strategy_config.symbol)
            self.comboBox.setCurrentText(self.strategy_config.timeframe)
            self.comboBox_2.setCurrentText(self.strategy_config.timeframe_filter)
            self.spinBox.setValue(self.strategy_config.risk_amount)
            self.checkBox.setChecked(self.strategy_config.auto)
            self.checkBox_2.setChecked(self.strategy_config.buy_only)
            self.checkBox_3.setChecked(self.strategy_config.sell_only)
            self.checkBox_4.setChecked(self.strategy_config.noti_telegram)
            self.spinBox_2.setValue(strategy_config.max_total_orders)
            self.spinBox_3.setValue(strategy_config.unit_factor)

    def lineEdit_textChanged(self, value: str):
        self.lineEdit.setText(value.upper())

        unit_factor = 0
        if value.startswith('BTC'):
            unit_factor = 0
        elif value.startswith('XAU'):
            unit_factor = 100
        else:
            unit_factor = 100000
        self.spinBox_3.setValue(unit_factor)

    def checkBox_stateChanged(self):
        value: bool = not self.checkBox.isChecked()
        self.label.setEnabled(value)
        self.spinBox.setEnabled(value)
        self.label_2.setEnabled(not value)
        self.spinBox_2.setEnabled(not value)

    def pushButton_clicked(self):
        params = {
            'symbol': self.lineEdit.text(),
            'timeframe': self.comboBox.currentText(),
            'timeframe_filter': self.comboBox_2.currentText(),
            'risk_amount': self.spinBox.value(),
            'unit_factor': self.spinBox_3.value(),
            'auto': self.checkBox.isChecked(),
            'max_total_orders': self.spinBox_2.value(),
            'buy_only': self.checkBox_2.isChecked(),
            'sell_only': self.checkBox_3.isChecked(),
            'noti_telegram': self.checkBox_4.isChecked()
        }

        config_manager = JsonFileManager('config.json', self.rw_lock)
        with config_manager.load_and_update_config() as config:
            try:
                strategy_config = TradingStrategyConfig(**params)

                if self.strategy_config is not None:
                    strategy_config.is_running = self.strategy_config.is_running
                    strategy_config.next_search_signal_time = self.strategy_config.next_search_signal_time
                    strategy_config.position = self.strategy_config.position

                config.update({strategy_config.symbol: strategy_config.model_dump(exclude='symbol')})
            except ValidationError as ex:
                QMessageBox.critical(self, 'Thông báo', ex.errors()[0]['msg'])
            