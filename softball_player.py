from typing import Dict, Set

class Player:
    name: str
    positions: Set[str]
    positions_stengths: Dict[str, int]
    available: bool
    innings_played: int
    late: bool
    female: bool

    def __init__(self, name, available, female, late, positions, strengths):
        
        assert len(positions) == len(strengths), f"{name} has mismatched number of positions and strengths"
        # assert len(positions) > 0, f"{name} cannot play 0 positions"

        self.name = name
        self.available = available
        self.late = late
        self.innings_played = 0 # start at 0 for now
        self.female = female

        self.positions = set(positions)
        self.positions_stengths = {}
        for i in range(len(positions)):
            self.positions_stengths[positions[i]] = strengths[i]

    def try_update_positions(self, from_pos, to_pos):
        if from_pos in self.positions:
            self.positions.remove(from_pos)
            str = self.positions_stengths.pop(from_pos)
            self.positions.add(to_pos)
            self.positions_stengths[to_pos] = str

    def __repr__(self):
        return f"{self.name} ({self.innings_played})- Female: {self.female};  Available: {self.available};  Late: {self.late};  {self.positions_stengths}\n"