from typing import Dict, List
from softball_models.player import Player
from softball_models.positions import Position

class Inning:
    def __init__(self, bench: List[Player], late: List[Player]):
        self.bench: Dict[str, Player] = {p.name: p for p in bench}
        self.late: List[Player] = late
        self.field: Dict[Position, Player] = {}
        self.females_playing: int = 0
        self.playing_count: int = 0
        self.strength: float = 0

    def __str__(self):
        res = f"{self.number}\n"

        res += f"\tPlaying:\n"
        for k,v in self.field.items():
            res += f"\t\t{k} {v.name}\n"

        res += f"\tSitting:\n"
        for k,v in self.bench.items():
            res += f"\t\t{k}\n"
        return res
    
    