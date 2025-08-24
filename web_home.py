import streamlit as st
from softball_beam_schedule import BeamSchedule, get_all_lineups_by_score, get_percentile_item
from softball_data import load_players_from_csv, players_to_df, dataframe_to_players, get_default_players
from softball_player import Player
from softball_schedule import Schedule, ScheduleConfig
from typing import List
from streamlit_ext import CsvUploader, DataTable
from web_schedule_options import render_schedule_options
from web_players import render_players
from web_schedule import render_schedule
from softball_positions import get_positions


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
            schedule: Schedule = Schedule.create(players, schedule_config)

            # players = players
            # for p in players:
                # p.innings_played = 0

            BeamSchedule.create(5, 6, players, schedule_config)

            render_schedule(schedule)

    print("Finish")