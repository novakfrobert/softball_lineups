
from enum import Enum


class SchedulerType(Enum):
    GREEDY = "Greedy"
    BEAM   = "Beam"


class ScheduleConfig:
    number_innings: int = 6
    females_required: int = 3
    players_required: int = 10
    inning_of_late_arrivals: int = 3
    schedule_type: SchedulerType = SchedulerType.GREEDY