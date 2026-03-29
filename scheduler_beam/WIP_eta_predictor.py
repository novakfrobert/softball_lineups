import math
import os
from typing import Dict, List

import matplotlib.pyplot as plt
import statistics
from collections import deque
import heapq
from math import exp, log, log2, sqrt
import time

from utils.debug import dbg
from utils.math import clamp
from utils.rolling_window import RollingWindow


def slope(points: dict):
    if len(points) < 2:
        return 0.0

    xs, ys = zip(*sorted(points.items()))
    n = len(xs)

    mean_x = sum(xs) / n
    mean_y = sum(ys) / n

    num = sum((x - mean_x) * (y - mean_y) for x, y in zip(xs, ys))
    den = sum((x - mean_x) ** 2 for x in xs)

    return num / den if den != 0 else 0.0


def correlation(points: dict):
    if len(points) < 2:
        return 0.0

    xs, ys = zip(*sorted(points.items()))
    n = len(xs)

    mean_x = sum(xs) / n
    mean_y = sum(ys) / n

    cov = sum((x - mean_x) * (y - mean_y) for x, y in zip(xs, ys))
    var_x = sum((x - mean_x) ** 2 for x in xs)
    var_y = sum((y - mean_y) ** 2 for y in ys)

    den = sqrt(var_x * var_y)

    return cov / den if den != 0 else 0.0



def remove_outliers_mean_dict(data: dict, k=1):
    if len(data) < 2:
        return data

    values = list(data.values())

    mean = statistics.mean(values)
    stdev = statistics.pstdev(values)

    if stdev == 0:
        return data

    return {
        t: v
        for t, v in data.items()
        if abs(v - mean) <= k * stdev
    }

def remove_outliers_mean(data, k=1):
    if len(data) < 2:
        return data

    mean = statistics.mean(data)
    stdev = statistics.pstdev(data)

    if stdev == 0:
        return data

    return [x for x in data if abs(x - mean) <= k * stdev]

def bottom_percent(d, pct=0.95):
    if not d:
        return []
    k = max(1, int(len(d) * pct))
    return heapq.nsmallest(k, d)

def top_percent(d, pct=0.95):
    if not d:
        return []
    k = max(1, int(len(d) * pct))
    return heapq.nlargest(k, d)

def middle_percent(d, pct=0.4):
    s = sorted(d)
    drop = int(len(s) * (1 - pct) / 2)
    return s[drop:len(s)-drop]

def time_to_position(dx, v0, a, eps=1e-12):
    if abs(a) < eps:  # treat as constant velocity
        if abs(v0) < eps:
            return None  # will never reach target
        return dx / v0

    disc = v0*v0 + 2*a*dx
    if disc < 0:
        return None

    return (-v0 + sqrt(disc)) / a

from collections import deque
import time


class WeightedDeque(deque):
    def __init__(self, maxlen, dt=0.1, decay=1.0):
        """
        maxlen : number of samples stored
        dt     : seconds represented by each sample
        decay  : exponential decay constant
        """
        super().__init__(maxlen=maxlen)
        self.dt = dt
        self.decay = decay

    def weighted_avg(self):
        n = len(self)
        if n == 0:
            return 0

        weighted_sum = 0
        weight_sum = 0

        for i, v in enumerate(self):
            age = (n - 1 - i) * self.dt
            w = exp(-self.decay * age)

            weighted_sum += v * w
            weight_sum += w

        return weighted_sum / weight_sum


class ETAPredictor:
    def __init__(self, alpha: float):
        self.alpha = alpha
        self.start_time = None
        self.last_time = self.start_time
        self.last_progress = 0.0
        self.time_elapsed = 0.0

        self.last_velocity = 0.0
        self.last_acceleration = 0.0
        self.last_eta = 0.0

        self.dr = 0.0
        self.v0 = 0.0

        # self.rates = WeightedDeque(100)
        self.recent_progress = RollingWindow(window_seconds=30)
        self.recent_velocities = RollingWindow(window_seconds=5)
        self.recent_velocities2 = RollingWindow(window_seconds=12)
        self.recent_accelerations = RollingWindow(window_seconds=1)
        self.recent_accelerations2 = RollingWindow(window_seconds=1)
        self.recent_ts = RollingWindow(window_seconds=1)
        self.recent_jerks = deque(maxlen=3)

        self.velocities = {}
        self.times = {}
        self.velocities2 = {}
        self.accelerations = {}
        self.progresses = {}

        self.rolling_etas = RollingWindow(window_seconds=1)

        self.etas: Dict[int, List[float]] = {}
        self.r_etas: Dict[int, List[float]] = {}

        self.count = 0

  
    def _get_avgs(self, list, f = lambda x: x):
        vals = f(list)
        if vals:
            return sum(vals) / len(vals)
        else: 
            return sum(list) / len(list)
    
    def _get_avg(self, value, list, f = lambda x: x):
        list.append(value)
        vals = f(list)
        if vals:
            return sum(vals) / len(vals)
        else: 
            return sum(list) / len(list)
    
    def _linear_predictor(self, rate: float, remaining: float):
        ans = remaining / rate
        if ans >= 0:
            return ans
        return None

    def _get_smoothed_rate(self, dp: float, dt: float):
        rate = dp / dt

        avg_rate = self._get_avg(rate, self.rates, lambda x: bottom_percent(x, 0.8))
        avg_avg_rate = self._get_avg(avg_rate, self.avg_rates, lambda x: x)

        return avg_rate

    
    def update_alpha(self, velocity, slope_v):
        """
        Update alpha using velocity acceleration trend (slope_v).
        """

        if not hasattr(self, "alpha"):
            self.alpha = 20.0  # start assuming strong slow-start/fast-finish

        # normalize acceleration
        norm_accel = slope_v / max(abs(velocity), 1e-6)

        linear = 1

        # squash to stable range
        gain = 10.0
        signal = math.tanh(norm_accel * gain)

        # map to alpha target
        alpha_target = linear + 4.0 * max(0.0, signal)

        # time decay toward linear if no sustained acceleration
        decay = math.exp(-self.time_elapsed / 50.0)
        alpha_target = linear + (alpha_target - linear) * (1 - decay)

        # smooth update
        smoothing = 0.3
        self.alpha = (1 - smoothing) * self.alpha + smoothing * alpha_target

        # clamp
        self.alpha = clamp(self.alpha, 1.0, 10.0)

        return self.alpha
    
    # def update(self, progress_percent):

    #     now = time.perf_counter()

    #     if not self.start_time:
    #         self.last_progress = progress_percent
    #         self.start_time = now
    #         self.last_time = now
    #         return
        
    #     dt = now - self.last_time
    #     self.time_elapsed += dt
    #     self.last_time = now

    #     self.progresses[self.time_elapsed] = progress_percent
    #     self.recent_progress.append(progress_percent)

    #     oldest = self.recent_progress.oldest()
    #     dp = (progress_percent - oldest[1])
    #     dt = (now - oldest[0])
    #     velocity = dp / dt

    #     self.recent_velocities.set_window(clamp(self.time_elapsed/3, 1, 30))
    #     self.recent_velocities.append(velocity)
    #     self.velocities[self.time_elapsed] = velocity

    #     slope_v = max(0, slope(self.recent_velocities))

    #     alpha = self.update_alpha(velocity, slope_v)

    #     effective_rate = dp / max(math.log(dt, alpha), 1e-6)
    #     eta = (100 - progress_percent) / max(effective_rate, 1e-6)

    #     r_eta = self._get_avg(eta, self.rolling_etas)

    #     self.r_etas[self.time_elapsed] = r_eta
    #     self.etas[self.time_elapsed] = eta

    #     dbg(r_eta, eta, progress_percent, self.time_elapsed, velocity, alpha, slope_v, slope_v)

    #     return eta
    
    

    def update(self, progress_percent):

        now = time.perf_counter()

        if not self.start_time:
            self.last_progress = progress_percent
            self.start_time = now
            self.last_time = now
            return
        
        dt = now - self.last_time
        self.time_elapsed += dt
        self.last_time = now

        self.progresses[self.time_elapsed] = progress_percent
        self.recent_progress.append(progress_percent)

        oldest = self.recent_progress.oldest()
        velocity = (progress_percent - oldest[1]) / (now - oldest[0])

        self.recent_velocities.append(velocity)

        self.velocities[self.time_elapsed] = velocity

        slope_v = max(0, slope(self.recent_velocities))
       
        self.alpha = self.update_alpha(velocity, slope_v)

        t = (100 / velocity) ** 1/(self.alpha)
        eta = max(1, t - self.time_elapsed)

        self.velocities[self.time_elapsed] = velocity
        self.recent_ts.append(t)

        self.rolling_etas.set_window(clamp(t/10, 1, 30))
        r_eta = self._get_avg(eta, self.rolling_etas)

        self.r_etas[self.time_elapsed] = r_eta
        self.etas[self.time_elapsed] = eta

        dbg(r_eta, eta, progress_percent, self.time_elapsed, t, velocity, self.alpha, slope_v)

        return eta
    
    


    # def update(self, progress_percent):
    #     """
    #     progress_percent: float in [0, 100]
    #     returns ETA seconds
    #     """

    #     now = time.perf_counter()
        

    #     #
    #     # Start time on the first call to update
    #     #
    #     if not self.start_time:
    #         self.last_progress = progress_percent
    #         self.start_time = now
    #         self.last_time = now
    #         return
        
    #     dp = progress_percent - self.last_progress
    #     dt = now - self.last_time

    #     self.time_elapsed += dt
    #     self.last_progress = progress_percent
    #     self.last_time = now

    #     self.count += 1

    #     remaining = 100 - progress_percent

    #     self.recent_progress.append(progress_percent)

    #     oldest = self.recent_progress.oldest()

    #     velocity = (progress_percent - oldest[1]) / (now - oldest[0])

    #     acceleration = slope(remove_outliers_mean_dict(self.velocities, 2))

    #     if velocity == 0:
    #         velocity = 1E-12

    #     eta = None
    #     mode = None
    #     distance = remaining
    #     if geometric:= time_to_position(distance, velocity, acceleration):
    #         mode = "geometric"
    #         eta = geometric

    #     elif linear:= self._linear_predictor(velocity, remaining):
    #         mode = "linear"
    #         eta = linear
        
    #     else:
    #         mode = "avg"
    #         eta = remaining / velocity

    #     self.rolling_etas 
    #     eta_avg = self._get_avg(eta, self.rolling_etas, lambda x: bottom_percent(x, 0.8))

    #     instant_velo = dp/dt
    #     dbg(dt, instant_velo, velocity, acceleration, remaining, self.time_elapsed)

    #     if self.time_elapsed < 3:
    #         return None

    #     self.velocities[self.time_elapsed] = velocity
    #     self.velocities2[self.time_elapsed] = dp/dt
    #     self.accelerations[self.time_elapsed] = acceleration

        
    #     self.etas[self.time_elapsed] = eta
    #     self.r_etas[self.time_elapsed] = eta_avg
       
    #     return eta
