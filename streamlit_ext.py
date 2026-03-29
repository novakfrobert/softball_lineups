from math import log
import time

import streamlit as st

from utils.debug import dbg
from utils.math import clamp

class CsvUploader:

    @staticmethod
    def upload(text: str, key: str = None):

        if not key:
            key = text

        session_key = CsvUploader._get_session_key(key)

        iteration = 0
        if session_key in st.session_state:
            iteration = st.session_state[session_key]
        else:
            st.session_state[session_key] = iteration

        widget_key = f"{session_key}{iteration}"
        file = st.file_uploader("Upload CSV", type="csv", key=widget_key)

        new = False
        session_file_key = f"file_{widget_key}"
        if file and file != st.session_state.get(session_file_key, ""):
            st.session_state[session_file_key] = file
            new = True

        return file, new
    
    @staticmethod
    def clear(key_str: str):
        key = CsvUploader._get_session_key(key_str)
        if key in st.session_state:
            st.session_state[key] += 1

    @staticmethod
    def _get_session_key(key_str: str):
        return f"file_uploader_key_{key_str}"

class DataTable:
    @staticmethod
    def edit(data, to_df=None, to_data=None, on_clear=None, on_add=None, on_remove=None):

        clear_col, add_col, del_col, padding = st.columns([1,1,1,4])

        with clear_col:
            if st.button("Clear Table", type="primary"):
                on_clear()

        with add_col:
            if st.button("Add Row"):
                on_add()

        with del_col:
            if st.button("Delete Rows"):
                on_remove()
        
        if to_df:
            data = to_df(data)
        edited_df = st.data_editor(data, num_rows="fixed", use_container_width=True)
        if to_data:
            data = to_data(edited_df)

        return data
    
class ProgressReporter:

    def __init__(self, msg: str):
        self.total_progress: float = 0
        self.msg: str = msg
        self.progress_bar = None
        self.update_threshold_pct = 0.02
        self.update_threshold_time = .1
        self.last_updated_pct = 0
        self.last_updated_ui = 0
        self.last_updated_time = 0

    def __enter__(self):
        self.progress_bar = st.progress(0, self.msg)
        return self

    def __exit__(self, exc_type, exc_value, traceback):
        self.progress_bar.empty()

    @staticmethod
    def create(msg: str):
        return ProgressReporter(msg)

    def __call__(self, inc_progress: float, msg: str = "Default"):

        now = time.perf_counter()

        self.total_progress += inc_progress
        percent =  self.total_progress * 100

        d_pct = self.total_progress - self.last_updated_pct
        d_time = now - self.last_updated_time
        
        if d_time < self.update_threshold_time:
            return
        
        if msg == "Default":
            self.msg = f"{percent:.2f}% complete."
            # print(self.msg)
        elif msg:
            self.msg = msg

        self.last_updated_pct = self.total_progress
        self.last_updated_time = now

        if now - self.last_updated_ui < 0.1:
            return

        self.progress_bar.progress(self.total_progress, text=self.msg)
        self.last_updated_ui = now


