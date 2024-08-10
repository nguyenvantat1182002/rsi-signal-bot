import MetaTrader5 as mt5

from PyQt5.QtWidgets import QApplication
from windows import EditWindow


if mt5.initialize():
    app = QApplication([])

    win = EditWindow()
    win.show()

    app.exec_()
    
mt5.shutdown()
