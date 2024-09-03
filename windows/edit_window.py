import os
import MetaTrader5 as mt5

from pydantic import ValidationError
from typing import Optional
from windows.models import TradingStrategyConfig, Config
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
        self.checkBox_5.stateChanged.connect(self.checkBox_5_stateChanged)
        self.checkBox_6.stateChanged.connect(self.checkBox_6_stateChanged)
        self.checkBox_7.stateChanged.connect(self.checkBox_7_stateChanged)
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
            self.doubleSpinBox_3.setValue(self.strategy_config.risk_amount)
            self.comboBox_3.setCurrentText(self.strategy_config.risk_type)
            self.checkBox_2.setChecked(self.strategy_config.buy_only)
            self.checkBox_3.setChecked(self.strategy_config.sell_only)
            self.spinBox_3.setValue(strategy_config.unit_factor)
            self.checkBox_5.setChecked(self.strategy_config.hedging_mode)
            self.doubleSpinBox.setValue(self.strategy_config.default_volume)
            self.spinBox_4.setValue(self.strategy_config.atr_multiplier)
            self.doubleSpinBox_2.setValue(self.strategy_config.risk_reward)
            self.checkBox_6.setChecked(self.strategy_config.use_default_volume)
            self.checkBox_7.setChecked(self.strategy_config.use_risk_reward)

    def checkBox_5_stateChanged(self):
        self.checkBox_7.setChecked(self.checkBox_5.isChecked())
        
    def checkBox_7_stateChanged(self):
        value: bool = self.checkBox_7.isChecked()

        self.doubleSpinBox_2.setEnabled(value)

        if not value and self.checkBox_5.isChecked():
            self.checkBox_5.setChecked(False)

    def checkBox_6_stateChanged(self):
        value: bool = self.checkBox_6.isChecked()

        self.doubleSpinBox.setEnabled(value)
        
        self.label.setEnabled(not value)
        self.spinBox.setEnabled(not value)
        self.comboBox_3.setEnabled(not value)

    def lineEdit_textChanged(self, value: str):
        unit_factor = 0
        if value.startswith('BTC'):
            unit_factor = 0
        elif value.startswith('XAU'):
            unit_factor = 100
        else:
            unit_factor = 100000
        self.spinBox_3.setValue(unit_factor)

    def pushButton_clicked(self):
        params = {
            'symbol': self.lineEdit.text(),
            'timeframe': self.comboBox.currentText(),
            'timeframe_filter': self.comboBox_2.currentText(),
            'risk_amount': self.doubleSpinBox_3.value(),
            'risk_type': self.comboBox_3.currentText(),
            'unit_factor': self.spinBox_3.value(),
            'buy_only': self.checkBox_2.isChecked(),
            'sell_only': self.checkBox_3.isChecked(),
            'hedging_mode': self.checkBox_5.isChecked(),
            'default_volume': self.doubleSpinBox.value(),
            'atr_multiplier': self.spinBox_4.value(),
            'risk_reward': self.doubleSpinBox_2.value(),
            'use_default_volume': self.checkBox_6.isChecked(),
            'use_risk_reward': self.checkBox_7.isChecked(),
        }

        config = Config(self.rw_lock)
        with config.load_and_update() as config:
            try:
                strategy_config = TradingStrategyConfig(**params)

                if self.strategy_config is not None:
                    strategy_config.is_running = self.strategy_config.is_running
                    strategy_config.next_search_signal_time = self.strategy_config.next_search_signal_time
                    strategy_config.position = self.strategy_config.position

                config.update({
                    strategy_config.symbol: strategy_config.model_dump(exclude='symbol')
                })
            except ValidationError as ex:
                QMessageBox.critical(self, 'Thông báo', ex.errors()[0]['msg'])
            