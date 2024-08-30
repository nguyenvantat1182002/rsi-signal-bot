import os
import json

from typing import Generator
from contextlib import contextmanager
from datetime import datetime, date
from PyQt5.QtCore import QReadWriteLock


def serialize_date_to_iso(o):
    if isinstance(o, (date, datetime)):
        return o.isoformat()


class Config:
    def __init__(self, rw_lock: QReadWriteLock):
        self.file_path = os.path.join(os.getcwd(), 'config.json')
        self.rw_lock = rw_lock

    def get(self) -> dict:
        self.rw_lock.lockForRead()
        try:
            config = {}

            if os.path.exists(self.file_path):
                with open(self.file_path, encoding='utf-8') as file:
                    config = json.load(file)

            return config
        finally:
            self.rw_lock.unlock()

    @contextmanager
    def load_and_update(self) -> Generator[dict, None, None]:
        config = {}

        self.rw_lock.lockForRead()
        try:
            if os.path.exists(self.file_path):
                with open(self.file_path, encoding='utf-8') as file:
                    config = json.load(file)
            
            yield config
        finally:
            self.rw_lock.unlock()
            
        self.update(config)
    
    def update(self, data: dict):
        self.rw_lock.lockForWrite()
        try:
            with open(self.file_path, 'w', encoding='utf-8') as file:
                json.dump(data, file, indent=4, default=serialize_date_to_iso)
        finally:
            self.rw_lock.unlock()
