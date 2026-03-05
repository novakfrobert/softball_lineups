import sys
import traceback
import streamlit as st
from softball_beam_schedule import BeamSchedule, get_all_lineups_by_score, get_percentile_item
from data.softball_data import load_players_from_csv, players_to_df, dataframe_to_players, get_default_players
from softball_models.player import Player
from softball_models.schedule_config import ScheduleConfig
from scheduler_greedy import GreedySchedule
from typing import List
from web_schedule_options import render_schedule_options
from web_players import render_players
from web_schedule import render_schedule


def render_home():

    print()
    print()
    print("New Render")

    if "players" not in st.session_state:
        st.session_state.players = get_default_players()

    players: List[Player] = st.session_state.players
    print("from state", players)

    st.set_page_config(
        page_title="Softball Lineup",     # 📝 Tab title
        page_icon="🥎",                   # 🖼️ Emoji or path to image
        layout="wide"                     # Full-width layout
    )

    with st.container():
        col_main_padding_left, col_main, col_main_padding_right = st.columns([2, 10, 2])  # middle column wider

        with col_main:
            players = render_players(players)
            
        with st.sidebar:
            schedule_config: ScheduleConfig = render_schedule_options(players)

        with col_main:
            schedule: GreedySchedule = GreedySchedule.create(players, schedule_config)

            # players = players
            # for p in players:
                # p.innings_played = 0

            fairness_index = 2
            sigma_weight = 2
            try:
                BeamSchedule.create(sigma_weight, fairness_index, players, schedule_config)
            except Exception as e:
                print("Beam schedule failed:", e)
                print(traceback.print_exc(file=sys.stdout) )
                print("continuing from failed beam schedule...")

            render_schedule(schedule)

    print("Finish")