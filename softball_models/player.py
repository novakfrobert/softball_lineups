from typing import Dict, Set

from softball_models.positions import Position

import itertools
_counter = itertools.count()

class Player:
    name: str
    positions: Set[Position]
    positions_stengths: Dict[Position, int]
    available: bool
    innings_played: int
    late: bool
    female: bool
    id: int

    def __init__(self, name, available, female, late, positions, strengths, id=None):
        
        assert len(positions) == len(strengths), f"{name} has mismatched number of positions and strengths"
        # assert len(positions) > 0, f"{name} cannot play 0 positions"

        if id is None:
            self.id = next(_counter)
        else:
            self.id = id
        self.name = name
        self.available = available
        self.late = late
        self.female = female

        self.positions = set(positions)
        self.positions_stengths = {}
        for i in range(len(positions)):
            self.positions_stengths[positions[i]] = strengths[i]

    def __repr__(self):
        return f"{self.name} [{self.id}] - Female: {self.female};  Available: {self.available};  Late: {self.late};  Positions: {self.positions_stengths}\n"
    
    def __eq__(self, other):
        if not isinstance(other, Player):
            return NotImplemented
        return self.id == other.id

    def __hash__(self):
        return hash(self.id)