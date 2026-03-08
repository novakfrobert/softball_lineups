from softball_models.schedule import Schedule


def validate(schedule: Schedule):

    not_enough_females = []
    not_enough_players = []

    for inning in schedule.innings:
        for pos, player in inning.field.items():
            if pos not in player.positions:
                schedule.warnings.append(f"{player.name} is playing {pos} at random in inning {inning.id}.")
        
        if inning.playing_count < schedule.config.players_required:
            not_enough_players.append(inning.id)

        if inning.females_playing < schedule.config.females_required:
            not_enough_females.append(inning.id)

    if not_enough_females:
        schedule.warnings.append(f"Not enough females in the following innings: {not_enough_females}")

    if not_enough_players:
        schedule.warnings.append(f"Not enough players in the following innings: {not_enough_players}")

