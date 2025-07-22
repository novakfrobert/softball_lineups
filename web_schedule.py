import streamlit as st
from softball_player import Player
from softball_schedule import Schedule
from typing import List


def render_schedule(schedule: Schedule):
    col_padding_left, col_count, col_padding_mid, col_lineup, col_padding_right = st.columns([0.3, 2, 1, 10, 1])
    with col_count:
        if schedule.warnings: st.subheader("⚠️ Warnings")
        for warning in schedule.warnings:
            st.write(f"⚠️{warning}")

        available_players: List[Player] = [p for p in schedule.players if p.available]
        available_players.sort(key=lambda p: p.innings_played)
        avg_score = round(sum(inning.score for inning in schedule.innings) / len(schedule.innings), 2)
        st.subheader("Innings Played")
        st.markdown(f"<b>Avg Score:</b> <small>{avg_score}</small>", unsafe_allow_html=True)
        st.code('\n'.join([f"{p.innings_played} {p.name}" for p in available_players]), line_numbers=False)

    with col_lineup:
        st.subheader("📜 Lineups by Inning")

        for inning in schedule.innings:
            st.header(f"Inning {inning.number}", divider=True)
            playing = '\n'.join([f"{pos} {player.name}" for pos, player in inning.positions.items()])
            sitting = '\n'.join([f"{name}" for name in inning.bench])
            late = '\n'.join([f"{player.name}" for player in inning.late])

            if not sitting: sitting = "None"
            if not late: late = "None"

            col_stats, col_playing, col_sitting, col_late = st.columns([2,3,3,3])
            with col_playing:
                st.markdown("##### 🟢 Playing:")
                st.code(playing, line_numbers=False)
            with col_sitting:
                st.markdown("##### 🔴 Sitting:")
                st.code(sitting, line_numbers=False)
            with col_late:
                st.markdown("##### 🟡 Late:")
                st.code(late, line_numbers=False)
            with col_stats:
                st.markdown(f"<b>Score:</b> <small>{inning.score}</small>", unsafe_allow_html=True)
                st.markdown(f"<b>Females:</b> <small>{inning.females_playing}</small>", unsafe_allow_html=True)
                st.markdown(f"<b>Players:</b> <small>{inning.playing_count}</small>", unsafe_allow_html=True)

