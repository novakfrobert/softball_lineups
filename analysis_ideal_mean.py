import numpy as np
import matplotlib.pyplot as plt
import statistics

"""
# As an example

max_lineup = 85

n = 6   # number of innings
r = 3   # remaining innings

scores = [
    70, # first inning
    73, # second inning
    80  # third inning
]

# Partial values through 3 innings
sum_p  = 223
ssd_p  = 52.666   # sum of squared deviations
std_p  = 4.1899   # = (ssd_p / (n-r)) ^ (1/2)  = sqr root of ssd divided by num innings so far
mean_p = 74.333

# Max acheivable sum
max_sum = sum_p + max_lineup*r
max_sum = 223 + 3*85
max_sum = 478

max_mean = max_sum / n
max_mean = 79.666

# Min acheivable std
min_std = (ssd_p / n)  ^ (1/2)   # assumes next 3 innings are equal to mean_p
min_std = 2.9627

# Caveat that this might be possible an impossible value to acheive given the current scores
# because its likely max_linup != mean_p
best_possible = max_sum - 2.0 * min_std
"""

def compute_result(max_innings, scores_so_far, value_for_remaining, sigma_weight):
    """
    Computes the result given:
    - max number of innings
    - scores already known
    - assumed value for every remaining inning

    Adjust the formula inside this function to match your own scoring logic.
    """
    n_so_far = len(scores_so_far)
    remaining = max_innings - n_so_far

    # Construct full list of inning values
    full_scores = np.array(scores_so_far + [value_for_remaining] * remaining, dtype=float)

    # Example scoring formula: total minus standard deviation
    total = full_scores.mean()
    sigma = full_scores.std()

    return total - sigma * sigma_weight


def plot_results(max_innings, scores_so_far, value_min, value_max, sigma_weight, num_points=2000):
    """
    Plots the result of compute_result() across a range of possible
    values for remaining innings.
    """
    # Build X axis (value assumed for remaining innings)
    value_range = np.linspace(value_min, value_max, num_points)

    # Compute results
    results = [compute_result(max_innings, scores_so_far, v, sigma_weight) for v in value_range]

    for i, r in enumerate(results):

        if r > 75.79:
            print(value_range[i])
            break

    # Plot
    plt.figure(figsize=(8, 5))
    plt.plot(value_range, results)
    plt.xlabel("Value used for remaining innings")
    plt.ylabel("Computed result")
    plt.title("Result vs Remaining Inning Value")
    plt.grid(True)
    plt.tight_layout()
    # plt.show()


def score(scores_so_far, ideal_mean, max_innings, weight):
    scores = scores_so_far + [ideal_mean]*(max_innings-len(scores_so_far))

    mean = statistics.mean(scores)
    stdev = statistics.stdev(scores)

    print(f"ideal: {ideal_mean}   mean: {mean}  stddev: {stdev}")

    return mean - weight*stdev

def calc_ideal_mean(scores_so_far, sigma_weight, max_linup):
    return (max_linup + statistics.mean(scores_so_far) * sigma_weight)  / (1 + sigma_weight)


"""
strenghts [np.float64(86.8), np.float64(78.8), np.float64(84.9)]
         best_score 75.79159992433397    equation res 78.12458186269247    value used 80.78159992433652   upper bound: 88.2   lower bound:  75.79159992433397
            """
# -----------------------------
# Example usage:
# -----------------------------
if __name__ == "__main__":
    max_innings = 6
    sigma_weight = 2
    scores_so_far = [86.8, 78.8, 84.9]  # Example known inning scores
    print("mean", sum(scores_so_far)/len(scores_so_far))
    # ideal_mean = calc_ideal_mean(scores_so_far, sigma_weight, 80)
    # print("ideal mean", ideal_mean)
    print("\tscore:",score(scores_so_far, 78.1245, 6, sigma_weight))
    print("\tscore:",score(scores_so_far, 80.7815, 6, sigma_weight))
    print("\tscore:",score(scores_so_far, 80.2815, 6, sigma_weight))
    print("\tscore:",score(scores_so_far, 79.7815, 6, sigma_weight))
    print("\tscore:",score(scores_so_far, 82.7815, 6, sigma_weight))
    print("\tscore:",score(scores_so_far, 81.7815, 6, sigma_weight))
    print("\tscore:",score(scores_so_far, 83.7815, 6, sigma_weight))
    print("\tscore:",score(scores_so_far, 84.7815, 6, sigma_weight))
    print("\tscore:",score(scores_so_far, 85.7815, 6, sigma_weight))
    print("\tscore:",score(scores_so_far, 86.7815, 6, sigma_weight))

    plot_results(max_innings, scores_so_far, value_min=50, value_max=200, sigma_weight=sigma_weight)


"""
Analysis shows a ideal (or good enough) mean to use for prediction would be

ideal_mean = clamp((max_lineup + (mean_p*sigma_weight)) / ( 1 + sigma_weight), min_lineup, max_lineup)

"""