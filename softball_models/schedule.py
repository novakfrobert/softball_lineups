from typing import List
from softball_models.player import Player
from softball_models.inning import Inning
from softball_models.positions import get_positions
from softball_models.schedule_config import ScheduleConfig

class Schedule: 
    players: List[Player]
    innings: List[Inning]

    config: ScheduleConfig
    positions: List[str]

    max_players: int = 10
    min_players: int = 8

    warnings: List[str]

    def __init__(self, players: List[Player], config: ScheduleConfig):
        self.players = players
        self.config = config
        self.innings = []
        self.positions = []
        self.warnings = []

    def _validate(self):

        not_enough_females = []
        not_enough_players = []

        for inning in self.innings:
            for pos, player in inning.positions.items():
                if pos not in player.positions:
                    self.warnings.append(f"{player.name} is playing {pos} at random in inning {inning.number}.")
            
            if inning.playing_count < self.config.players_required:
                not_enough_players.append(inning.number)

            if inning.females_playing < self.config.females_required:
                not_enough_females.append(inning.number)

        if not_enough_females:
            self.warnings.append(f"Not enough females in the following innings: {not_enough_females}")

        if not_enough_players:
            self.warnings.append(f"Not enough players in the following innings: {not_enough_players}")
    
  
    