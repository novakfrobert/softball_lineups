from enum import Enum
from typing import Callable, List

from scheduler.progress_callback import ProgressCallback
from scheduler.validation import validate
from scheduler_beam.beam_schedule import BeamScheduler
from scheduler_dp.dp_scheduler import DPScheduler
from scheduler_greedy.greedy_scheduler import GreedyScheduler
from softball_models.player import Player
from softball_models.schedule import Schedule
from softball_models.schedule_config import ScheduleConfig, SchedulerType



class ScheduleFactory:

    @staticmethod
    def create(players: List[Player], schedule_config: ScheduleConfig, progress_callback: ProgressCallback) -> Schedule:

        
        def create_greedy():
            return GreedyScheduler.create(players, schedule_config)

        def create_beam():
            return BeamScheduler.create(players, schedule_config, progress_callback)
        
        def create_dp():
            return DPScheduler.create(players, schedule_config)

        dispatcher = {
            SchedulerType.GREEDY: create_greedy,
            SchedulerType.BEAM: create_beam,
            SchedulerType.DP: create_dp,
        }

        schedule = dispatcher[schedule_config.schedule_type]()

        validate(schedule)

        return schedule

        



  
    