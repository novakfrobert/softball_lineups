from typing import Dict, List
from softball_models.player import Player
from softball_models.positions import Position

class Inning:
    number: int

    bench: Dict[str, Player] # key is name
    positions: Dict[Position, Player]

    late: List[Player] # key is name

    females_playing: int
    playing_count: int

    def __init__(self, n: int, bench: List[Player], late: List[Player]):
        self.number = n
        self.bench = {p.name: p for p in bench}
        self.late = late
        self.positions = {}
        self.females_playing = 0
        self.playing_count = 0
        self.score = 0

    def __str__(self):
        res = f"{self.number}\n"

        res += f"\tPlaying:\n"
        for k,v in self.positions.items():
            res += f"\t\t{k} {v.name}\n"

        res += f"\tSitting:\n"
        for k,v in self.bench.items():
            res += f"\t\t{k}\n"
        return res
    
    