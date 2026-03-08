from collections import defaultdict
from typing import Dict, List, Tuple

from softball_models.player import Player
from softball_models.schedule import Schedule


def get_play_counts(schedule: Schedule):
    play_counts = defaultdict(int)
    players_by_id = {p.id: p for p in schedule.players}

    for inning in schedule.innings:
        for pid in inning.playing_ids:
            play_counts[players_by_id[pid]] += 1

    return play_counts

def get_players_ordered_by_playcount(schedule: Schedule) -> List[Tuple[Player, int]]:
    play_count: Dict[Player, int] = get_play_counts(schedule)
    return sorted(play_count.items(), key=lambda x: -1*x[1])
