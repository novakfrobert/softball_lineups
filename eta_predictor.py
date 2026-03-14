import statistics
from collections import deque
import heapq
from math import log, log2, sqrt
import time

def bottom_percent(d, pct=0.95):
    if not d:
        return []
    k = max(1, int(len(d) * pct))
    return heapq.nsmallest(k, d)

def middle_percent(d, pct=0.4):
    s = sorted(d)
    drop = int(len(s) * (1 - pct) / 2)
    return s[drop:len(s)-drop]

def time_to_position(x0, xf, v0, a, eps=1e-12):
    dx = xf - x0

    if abs(a) < eps:  # treat as constant velocity
        if abs(v0) < eps:
            return None  # will never reach target
        return dx / v0

    disc = v0*v0 + 2*a*dx
    if disc < 0:
        return None

    return (-v0 + sqrt(disc)) / a

class ETAPredictor:
    def __init__(self, alpha=0.9, accel_bias=0.9):
        """
        alpha: smoothing for recent speed (0.2–0.4 works well)
        accel_bias: assumes algorithm speeds up later
        """
        self.alpha = alpha
        self.accel_bias = accel_bias

        self.start_time = None
        self.last_time = self.start_time
        self.last_progress = 0.0
        self.time_elapsed = 0.0

        self.last_r = 0.0
        self.last_pr = 0.0
        self.last_er = 0.0

        self.dr = 0.0
        self.dpr = 0.0
        self.der = 0.0

        self.rates = deque(maxlen=1000)
        self.d_rates = deque(maxlen=1000)

        self.last_eta = None
        self.last_eta_given_at = None

        self.etas = []

    def _get_average_rate(self):

        rates = bottom_percent(self.rates, 0.9)
        rate_ema = sum(rates) / len(rates)
        return rate_ema
        # return statistics.median(rates)
    
    def _get_average_d_rate(self):

        rates = middle_percent(self.d_rates, 0.9)
        rate_ema = sum(rates) / len(rates)
        # return statistics.median(rates)
        return rate_ema
    
    def _get_average_etas(self):
        return sum(self.etas) / len(self.etas)

    def update(self, progress_percent):
        """
        progress_percent: float in [0, 100]
        returns ETA seconds
        """

        now = time.perf_counter()

        if not self.start_time:
            self.start_time = now
            self.last_time = now

        dp = progress_percent - self.last_progress
        dt = now - self.last_time

        if dp <= 0 or dt <= 0:
            return None
        
        self.time_elapsed += dt

        rate = dp / dt  # percent per second

        self.rates.append(rate)

        avg_rate = self._get_average_rate()

        dr = (avg_rate - self.last_r)

        self.d_rates.append(dr)

        avg_der = self._get_average_d_rate()

        eta = time_to_position(progress_percent, 100, self.last_r, avg_der)

        if not eta:
            eta = self.last_eta

        self.last_progress = progress_percent
        self.last_time = now

        self.last_r = avg_rate

        if self.time_elapsed < 5:
            return None
        
        if self.last_eta is None:
            self.last_eta = eta
            self.last_eta_given_at = now
            self.etas = [eta]
            return eta

        if now - self.last_eta_given_at < 1:
            self.etas.append(eta)
            return self.last_eta

        avg_eta = self._get_average_etas()
        self.last_eta = avg_eta
        self.last_eta_given_at = now
        self.etas = [avg_eta]
            
        return avg_eta