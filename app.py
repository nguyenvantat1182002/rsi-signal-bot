import MetaTrader5 as mt5

from PyQt5.QtWidgets import QApplication
from windows import MainWindow


VERSION = 4

path = input('Path: ')
# path = r"C:\Program Files\MetaTrader 5 EXNESS\terminal64.exe"

if mt5.initialize(path=path):
    app = QApplication([])

    win = MainWindow(VERSION)
    win.show()

    app.exec_()
    
mt5.shutdown()
