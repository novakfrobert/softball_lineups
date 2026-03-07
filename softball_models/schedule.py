from typing import List
from softball_models.player import Player
from softball_models.inning import Inning
from softball_models.positions import get_position, get_positions
from softball_models.schedule_config import ScheduleConfig

class Schedule: 
    players: List[Player]
    innings: List[Inning]

    config: ScheduleConfig
    positions: List[str]

    warnings: List[str]

    def __init__(self):
        self.players = []
        self.config = None
        self.innings = []
        self.positions = []
        self.warnings = []

    def _validate(self):

        not_enough_females = []
        not_enough_players = []

        for inning in self.innings:
            for pos, player in inning.field.items():
                if pos not in player.positions:
                    self.warnings.append(f"{player.name} is playing {pos} at random in inning {inning.id}.")
            
            if inning.playing_count < self.config.players_required:
                not_enough_players.append(inning.id)

            if inning.females_playing < self.config.females_required:
                not_enough_females.append(inning.id)

        if not_enough_females:
            self.warnings.append(f"Not enough females in the following innings: {not_enough_females}")

        if not_enough_players:
            self.warnings.append(f"Not enough players in the following innings: {not_enough_players}")

    @classmethod
    def create(cls, *args, **kwargs):
        schedule: Schedule = cls._create_impl(*args, **kwargs)

        print("BASE METHOD")

        # Add a courtest catcher if there aren't enough players
        for inning in schedule.innings:
            if inning.playing_count <= 8:
                catcher = get_position("C")
                inning.field[catcher] = Player("⚠ COURTESY ⚠", True, False, False, [catcher], [1])

        schedule._validate()

        return schedule


    @classmethod
    def _create_impl(cls, *args, **kwargs):
        raise NotImplementedError


  
    