from collections import deque
import time
from typing import Callable


class RollingWindow(deque):
    def __init__(self, window_seconds=10):
        super().__init__()
        self.window = window_seconds

    def _trim(self):
        now = time.perf_counter()
        while super().__len__() and now - super().__getitem__(0)[0] > self.window:
            super().popleft()

    def append(self, value):
        super().append((time.perf_counter(), value))
        self._trim()

    def __iter__(self):
        self._trim()
        return (v for _, v in super().__iter__())

    def __getitem__(self, idx):
        self._trim()
        item = super().__getitem__(idx)
        if isinstance(idx, slice):
            return [v for _, v in item]
        return item[1]

    def __len__(self):
        self._trim()
        return super().__len__()
    
    def items(self):
        self._trim()
        return ((t, v) for t, v in super().__iter__())
    
    def keys(self):
        self._trim()
        return [k for k,_ in super().__iter__()]
    
    def values(self):
        self._trim()
        return [v for _,v in super().__iter__()]
    
    def newest(self):
        self._trim()
        return super().__getitem__(-1)
    
    def oldest(self):
        self._trim()
        return super().__getitem__(0)
    
    def set_window(self, window):
        self.window = window
        self._trim()

    def get_avg(self, f: Callable = None):
        vals = self.values()
        if f:
            vals = f(vals)
        if vals:
            return sum(vals) / len(vals)
        else: 
            return sum(list) / len(list)
        
    def per_second(self):
        return sum(self.values()) / self.window

