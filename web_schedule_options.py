import streamlit as st
from softball_player import Player
from softball_schedule import Schedule, ScheduleConfig
from typing import List


def render_schedule_options(players: List[Player]) -> ScheduleConfig:

    config = ScheduleConfig()

    number_players = len([p for p in players if p.available])
    number_females = len([p for p in players if p.female and p.available])

    number_innings = st.number_input("Number of Innings", min_value=1, max_value=10, value=6, key="num_innings")
    current_value = min(st.session_state.get("late_inning", 3), number_innings)
    inning_of_late_arrivals = st.number_input("Inning of Late Arrivals", min_value=1, max_value=number_innings, value=current_value, key="late_inning")

    st.divider()
    automatic_player_counts = st.toggle("Automatic player counts", True)

    if automatic_player_counts:
        max_players = 10 if number_females > 2 else 9
        st.session_state.min_players = max(8, min(max_players, number_players))
    minimum_players = st.number_input("Number Players", min_value=Schedule.min_players, max_value=Schedule.max_players, key="min_players", disabled=automatic_player_counts)

    if automatic_player_counts: 
        st.session_state.min_females = 3 if st.session_state.min_players > 9 else 2
    minimum_females = st.number_input("Minnimum Females", min_value=0, max_value=Schedule.max_players, key="min_females", disabled=automatic_player_counts)
    st.divider()

    config.number_innings = number_innings
    config.inning_of_late_arrivals = inning_of_late_arrivals
    config.females_required = minimum_females
    config.players_required = minimum_players
    return config

