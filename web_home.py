import sys
import traceback
import streamlit as st
from typing import List

from softball_models.player import Player
from softball_models.schedule import Schedule
from softball_models.schedule_config import ScheduleConfig

from scheduler.schedule_factory import ScheduleFactory
from services.player_service import get_default_players

from streamlit_ext import ProgressReporter
from utils.timing import reset_times
from web_schedule_options import render_schedule_options
from web_players import render_players
from web_schedule import render_schedule


def render_home():

    print()
    print()
    print("New Render")
    reset_times()

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

        with col_main, ProgressReporter.create("Creating schedule...") as progress:
            try:
                schedule = ScheduleFactory.create(players, schedule_config, progress)
                render_schedule(schedule)

            except Exception as e:
                st.write("Failed to create schedule.")
                print("Schedule failed:", e)
                print(traceback.print_exc(file=sys.stdout) )



    print("Finish")