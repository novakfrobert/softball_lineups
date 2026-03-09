from typing import Dict, List, Self

from scheduler.play_counter import PlayCounter
from softball_models.inning import Inning
import statistics

from softball_models.player import Player
from utils.timing import add_time

import time
import hashlib

class LineupNode:
    lineup: Inning | None # This is None for root node
    sigma: float # Standard deviation
    ssd: float   # Sum of squared deviation
    mean: float  
    cumulative_strength: float #strengths thus far
    cumulative_counts: PlayCounter # key is player name
    prev: Self
    next: List[Self]
    depth: int
    hash: str

    @staticmethod
    def root(players: List[Player]):
        root = LineupNode(None, None)
        root.hash = 0
        root.depth = 0
        root.sigma = 0
        root.ssd = 0
        root.mean = 0
        root.cumulative_strength = 0
        root.cumulative_counts = PlayCounter(players)

        return root

    def __init__(self, lineup: Inning, prev: Self):
        start = time.time()
        self.lineup = lineup
        self.prev = prev
        self.next = []

        if prev:
            self.depth = prev.depth + 1
            self.sigma = self._compute_sigma()
            self.cumulative_strength = prev.cumulative_strength + lineup.strength
            self.mean = self.cumulative_strength / self.depth
            self.ssd = (lineup.strength - self.mean)*(lineup.strength - prev.mean) + prev.ssd
            self.hash = self._hash()
            self.cumulative_counts = prev.cumulative_counts.copy()
            self.cumulative_counts.increment_many(lineup.field.values())

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


    def _compute_sigma(self):
        node: LineupNode = self.prev
        strengths = [self.lineup.strength]
        while node and node.lineup:
            strengths.append(node.lineup.strength)
            node = node.prev
        return statistics.pstdev(strengths)
    
    def __repr__(self):
        return f"Depth:{self.depth}  Strength:{self.cumulative_strength}  Counts:{self.cumulative_counts.counter},  Sigma{self.sigma}"
    