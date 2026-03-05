import time

times = {}
calls = {}

def reset_times():
    global times
    global calls

    times = {}
    calls = {}

def add_time(key, start):

    global times
    global calls

    if key not in times:
        times[key] = 0
        calls[key] = 0

    times[key] += time.time() - start
    calls[key] += 1

def print_times():
    global times
    global calls

    print(times)
    print(calls)