from typing import List

from scheduler_greedy.greedy_inning import GreedyInning
from softball_models.player import Player
from softball_models.positions import get_positions, get_position

from softball_models.schedule import Schedule
from softball_models.schedule_config import ScheduleConfig


class GreedySchedule(Schedule): 

    def _add_inning(self):
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

        inning = GreedyInning(number, bench, late)
        self.innings.append(inning)
        return inning
    
    @staticmethod
    def create(players: List[Player], config: ScheduleConfig):

        schedule = GreedySchedule(players, config)

        if config.players_required < 10:
            # remove lcf and rcf in favor of cf
            for player in players:
                player.try_update_positions("RCF", "RF")
                player.try_update_positions("LCF", "CF")

        # create schedule
        for _ in range(config.number_innings):

            inning: GreedyInning = schedule._add_inning()
            
            positions = get_positions(config.players_required)
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
                catcher = get_position("C")
                inning.positions[catcher] = Player("⚠ COURTESY ⚠", True, False, False, [catcher], [1])

        schedule._validate()

        return schedule
    