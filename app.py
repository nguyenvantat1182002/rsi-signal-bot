import MetaTrader5 as mt5

from PyQt5.QtWidgets import QApplication
from windows import MainWindow


VERSION = 4


if mt5.initialize():
    app = QApplication([])

    win = MainWindow(VERSION)
    win.show()

    app.exec_()
    
mt5.shutdown()
