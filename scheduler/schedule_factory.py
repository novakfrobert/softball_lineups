from enum import Enum
from typing import List

from scheduler.validation import validate
from scheduler_beam.beam_schedule import BeamScheduler
from scheduler_greedy.greedy_scheduler import GreedyScheduler
from softball_models.player import Player
from softball_models.schedule import Schedule
from softball_models.schedule_config import ScheduleConfig, SchedulerType



class ScheduleFactory:

    @staticmethod
    def create(players: List[Player], schedule_config: ScheduleConfig) -> Schedule:

        def create_greedy():
            return GreedyScheduler.create(players, schedule_config)

        def create_beam():
            return BeamScheduler.create(players, schedule_config)

        dispatcher = {
            SchedulerType.GREEDY: create_greedy,
            SchedulerType.BEAM: create_beam,
        }

        schedule = dispatcher[schedule_config.schedule_type]()

        validate(schedule)

        return schedule

        



  
    