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
        root.cumulative_strength = 0
        root.cumulative_counts = PlayCounter(players)

        return root

    def __init__(self, lineup: Inning, prev: Self):
        start = time.time()
        self.lineup = lineup
        self.prev = prev
        self.next = []

        if prev:
            prev.next.append(self)
            self.depth = prev.depth + 1
            self.hash = self._hash()
            self.cumulative_counts = prev.cumulative_counts.copy()
            self.cumulative_counts.increment_many(lineup.field.values())

        add_time("lineup node ctor", start)
    
    def get_stregnths(self):
        strengths = [self.lineup.strength]
        prev = self.prev
        while prev and prev.lineup:
            strengths.append(prev.lineup.strength)
            prev = prev.prev

        return strengths

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

    def __repr__(self):
        return f"Depth:{self.depth}  Strength:{self.cumulative_strength}  Counts:{self.cumulative_counts.counter},  Sigma{self.sigma}"
    
    def __eq__(self, other):
        if not isinstance(other, Player):
            return NotImplemented
        return self.hash == other.hash

    def __hash__(self):
        return hash(self.hash)
    