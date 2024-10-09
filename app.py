import MetaTrader5 as mt5
import os

from PyQt5.QtWidgets import QApplication
from windows import MainWindow


VERSION = 4

path = input('Path: ')
login = os.path.dirname(path).split('\\')[-1]

if mt5.initialize(path=path):
    app = QApplication([])

    win = MainWindow(login, VERSION)
    win.show()

    app.exec_()
    
mt5.shutdown()
