from windows.models import JsonFileManager
from PyQt5.QtCore import QThread, QReadWriteLock


class BaseThread(QThread):
    def __init__(self, rw_lock: QReadWriteLock):
        self.config_manager = JsonFileManager('config.json', rw_lock)
        super().__init__()

    