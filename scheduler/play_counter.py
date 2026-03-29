

from collections import defaultdict
from typing import List, Self

from softball_models.player import Player


class PlayCounter:

    def __init__(self, players: List[Player]):
        self.counter = {}
        self.add_players(players)

    def add_players(self, players: List[Player]):
        for p in players:
            self.add_player(p)

    def add_player(self, player: Player):
        self.counter[player.id] = 0

    def get_count(self, player: Player) -> int:
        return self.counter[player.id]
    
    def increment(self, player: Player):
        self.counter[player.id] += 1

    def increment_many(self, players: List[Player]):
        for p in players:
            self.increment(p)

    def least_played(self, subset: List[Player]) -> List[Player]:
        players_by_play_count = defaultdict(list)
        for player in subset:
            count = self.get_count(player)
            players_by_play_count[count].append(player)
            
        fewest: List[Player] = min(players_by_play_count.keys())

        return players_by_play_count[fewest]
    
    def copy(self) -> Self:
        new = PlayCounter([])
        new.counter = self.counter.copy()
        return new
    
    def rebase(self):
        minimum_value = min(self.counter.values())
        for key in self.counter.keys():
            self.counter[key] -= minimum_value

