import os
import MetaTrader5 as mt5

from PyQt5 import uic
from PyQt5.QtWidgets import QMainWindow, QCompleter
from PyQt5.QtGui import QStandardItem, QStandardItemModel


class EditWindow(QMainWindow):
    def __init__(self):
        super().__init__()
        uic.loadUi(os.path.join(os.getcwd(), 'ui', 'EditWindow.ui'), self)

        self.lineEdit.textChanged.connect(self.lineEdit_textChanged)
        self.checkBox.stateChanged.connect(self.checkBox_stateChanged)

        self.symbols_model  = QStandardItemModel()
        self.lineEdit.setCompleter(QCompleter(self.symbols_model, self))

        symbols = mt5.symbols_get()
        for item in symbols:
            self.symbols_model.appendRow(QStandardItem(item.name))

        self.timeframe_mapping = {
            '1M': mt5.TIMEFRAME_M1,
            '5M': mt5.TIMEFRAME_M5,
            '15M': mt5.TIMEFRAME_M15
        }

    def lineEdit_textChanged(self, value: str):
        self.lineEdit.setText(value.upper())

    def checkBox_stateChanged(self):
        value: bool = not self.checkBox.isChecked()
        self.label.setEnabled(value)
        self.spinBox.setEnabled(value)
        self.label_2.setEnabled(not value)
        self.spinBox_2.setEnabled(not value)