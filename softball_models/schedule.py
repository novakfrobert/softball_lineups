from collections import defaultdict
from typing import Dict, List, Tuple
from softball_models.player import Player
from softball_models.inning import Inning
from services.position_service import get_position, get_positions
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

