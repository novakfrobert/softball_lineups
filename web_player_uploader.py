import streamlit as st
from softball_player import Player
from softball_data import load_players_from_csv
from streamlit_ext import DataTable, CsvUploader
from typing import List

def render_player_uploader():
     
    key = "Upload Players CSV"
    file, new = CsvUploader.upload(key)
    if file and new:
        players = load_players_from_csv(file)
        st.session_state.players = players
        st.rerun()
        
    return key