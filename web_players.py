import streamlit as st
from softball_player import Player
from softball_data import  players_to_df, dataframe_to_players
from streamlit_ext import DataTable, CsvUploader
from typing import List
from web_player_uploader import render_player_uploader

def render_players(players: List[Player]):

    uploader_key = render_player_uploader()

    st.divider()

    st.subheader("🔧 Edit Players")
     
    def clear_players():
        print("CLEAR")
        CsvUploader.clear(uploader_key)
        st.session_state.players = []
        st.rerun()

    def add_player():
        players.insert(0, Player(f"Player_{len(players)+1}", True, False, False, [], []))

    return DataTable.edit(players, players_to_df, dataframe_to_players, clear_players, add_player)