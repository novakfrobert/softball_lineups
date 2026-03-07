from typing import Dict, List, Self

from softball_models.inning import Inning
import statistics

from utils.timing import add_time

import time
import hashlib
import math

class LineupNode:
    lineup: Inning | None # This is None for root node
    sigma: float # Standard deviation
    ssd: float   # Sum of squared deviation
    mean: float  
    cumulative_strength: float #strengths thus far
    cumulative_counts: Dict[str, int] # key is player name
    prev: Self
    next: List[Self]
    depth: int
    hash: str

    def __repr__(self):
        return f"Depth:{self.depth}  Strength:{self.cumulative_strength}  Counts:{self.cumulative_counts},  Sigma{self.sigma}"

    def __init__(self, lineup: Inning, prev: Self):
        start = time.time()
        self.lineup = lineup
        self.prev = prev
        self.next = []

        if prev:
            self.depth = prev.depth + 1
            self.sigma = self._compute_sigma()
            self.cumulative_counts = self._increment_counts()
            self.cumulative_strength = prev.cumulative_strength + lineup.strength
            self.mean = self.cumulative_strength / self.depth
            self.ssd = (lineup.strength - self.mean)*(lineup.strength - prev.mean) + prev.ssd
            self.hash = self._hash()

        add_time("lineup node ctor", start)

    def _hash(self):
        start = time.time()
        ids = []
        node: LineupNode | None = self
        while node.lineup is not None:
            ids.append(str(node.lineup.id))
            node = node.prev

        ids.sort()
        ids_str = " ".join(ids)
        hash = hashlib.sha256(ids_str.encode()).hexdigest()
        add_time("lineup node hash", start)
        return hash

    def _increment_counts(self):
        counts = self.prev.cumulative_counts.copy()
        for player in self.lineup.field.values():
            if player.id not in counts:
                counts[player.id] = 0
            counts[player.id] += 1
        return counts

    def _compute_sigma(self):
        node: LineupNode = self.prev
        strengths = [self.lineup.strength]
        while node and node.lineup:
            strengths.append(node.lineup.strength)
            node = node.prev
        return statistics.pstdev(strengths)
    
    def rebase_counts(self):
        minimum_value = min(self.cumulative_counts.values())
        for key in self.cumulative_counts.keys():
            self.cumulative_counts[key] -= minimum_value

    
    def projected_ideal_mean(self, min_lineup: float, max_lineup: float, sigma_weight: float):
        start = time.time()

        ideal_mean = (max_lineup + self.mean*sigma_weight) / (sigma_weight + 1)
        ideal_mean = clamp(ideal_mean, min_lineup, max_lineup)

        add_time("projected_ideal_mean", start)

        return ideal_mean

    def minimum_viable_score(self, max_depth, current_depth, ideal_mean, goal):
        ##
        # Create a minimum strength needed from the next lineup for this traversal to be viable
        #
        #  Given we've likely identified a best score thus far, a max depth, and a sigma weight:
        #  y             = best_score 
        #  n             = max_depth
        #  w             = sigma_weight
        #
        #  And our scoring function looks like:
        #  y             = mean - sigma_weight * updated_sigma
        #
        #  We can calculate our best case score at depth (max_depth - 1)
        #  and then decide what value, x, to add so we don't fall below our best score
        #  mean = (total(n-1) + x) / n
        #
        #  Sigma can be updated following the formula:
        #  Where SSD is the sum of squares SUM((xi - old_mean)^2)
        #  updated_sigma = sqrt(1/n * (ssd + (x - old_mean)*(x - new_mean))
        #  
        # Therefore:
        #  y  = (total(n-1) + x) / n - w * sqrt(1/n * (ssd + (x-p/(n-1)) * (x-(p+x)/n)))
        #
        #  When solving for x, this simplifies to a form of the quadratic formula, for which
        #  we will take the lower of the two numbers.
        #  
        ##
        start = time.time()

        remaining = max_depth - current_depth

        strengths = [self.lineup.strength] + [ideal_mean]*remaining
        node = self.prev
        while node and node.lineup:
            strengths.append(node.lineup.strength)
            node = node.prev

        cumulative = self.cumulative_strength + remaining*ideal_mean
        mean_0 = cumulative/(max_depth-1)
        s = 0
        for i in range(max_depth - 1):
            s += (strengths[i] - mean_0)**2

        w = 2.0
        n = max_depth
        p = cumulative
        y = goal

        w2 = w**2
        nw2 = n * w2
        a = nw2 - w2 - 1

        b = 2*n*y - 2*p*w2 - 2*p
        c = -n**2*y**2 - (p**2*w2)/(1 - n) + 2*n*p*y + n*s*w2 - p**2

        discriminant = b**2 - 4 * a * c
        
        res = (-math.sqrt(discriminant) - b) / (2 * a)
        add_time("minimum_viable_score", start)

        return res

def clamp(value, min_val, max_val):
    return max(min_val, min(value, max_val))