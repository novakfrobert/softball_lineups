from typing import List
from softball_player import Player
from softball_inning import Inning

class ScheduleConfig:
    number_innings: int = 6
    females_required: int = 3
    players_required: int = 10
    inning_of_late_arrivals: int = 3

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

    def get_positions(self):
        if self.config.players_required == 10:
            return ["P", "SS", "LF", "LCF", "3B", "1B", "2B", "RCF", "RF", "C"] # ordered by most important
        elif self.config.players_required == 9:
            return ["P", "SS", "LF", "CF", "3B", "1B", "2B", "RF", "C"] # ordered by most important
        elif self.config.players_required == 8:
            return ["P", "SS", "LF", "CF", "3B", "1B", "2B", "RF"] # ordered by most important
        else:
            raise Exception(f"Invalid number of players {self.players_required}")

    def add_inning(self):
        number = len(self.innings) + 1

        bench: List[Player] = []
        late: List[Player] = []
        for player in self.players:

            if not player.available:
                continue

            if player.late and number < self.config.inning_of_late_arrivals:
                late.append(player)
                continue

            bench.append(player)

        inning = Inning(number, bench, late)
        self.innings.append(inning)
        return inning
    
    def validate(self):

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
    
    @staticmethod
    def create(players: List[Player], config: ScheduleConfig):

        schedule = Schedule(players, config)

        if config.players_required < 10:
            # remove lcf and rcf in favor of cf
            for player in players:
                player.try_update_positions("RCF", "RF")
                player.try_update_positions("LCF", "CF")

        # create schedule
        for i in range(config.number_innings):

            inning: Inning = schedule.add_inning()
            
            positions = schedule.get_positions()
            for position in positions:

                if inning.must_be_female(config.players_required, config.females_required):
                    if inning.try_finding_female_player(position):
                        continue
                
                if inning.try_finding_optimal_player(position):
                    continue

                if inning.try_finding_any_player(position):
                    continue

            inning.optimize_lineup(positions)

            if config.players_required == 8:
                inning.positions["C"] = Player("⚠ COURTESY ⚠", True, False, False, ["C"], [0])

        schedule.validate()

        return schedule
    