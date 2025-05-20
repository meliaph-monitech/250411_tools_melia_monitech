import streamlit as st
st.set_page_config(page_title="Team Attendance", layout="wide")  # MUST be first Streamlit command

import json
import os
import time
from filelock import FileLock
from streamlit_autorefresh import st_autorefresh

# Refresh the app every 0.5 seconds
st_autorefresh(interval=500, key="auto_refresh")

# Configuration
NAMES = [
    "Alice", "Bob", "Charlie", "David",
    "Eve", "Faythe", "Grace", "Heidi",
    "Ivan", "Judy", "Mallory", "Niaj"
]
STATE_FILE = "attendance_state.json"
LOCK_FILE = "attendance_state.lock"

# Initialize state if not exists
def init_state():
    if not os.path.exists(STATE_FILE):
        with open(STATE_FILE, "w") as f:
            json.dump({name: False for name in NAMES}, f)

# Load state from file
def load_state():
    with FileLock(LOCK_FILE):
        with open(STATE_FILE, "r") as f:
            return json.load(f)

# Save state to file
def save_state(state):
    with FileLock(LOCK_FILE):
        with open(STATE_FILE, "w") as f:
            json.dump(state, f)

# Toggle the status of a name
def toggle_status(name):
    state = load_state()
    state[name] = not state[name]
    save_state(state)

# Run the app
def main():
    st.title("👥 Team Attendance Tracker")

    init_state()
    state = load_state()

    cols = st.columns(4)
    for i, name in enumerate(NAMES):
        col = cols[i % 4]
        status = state[name]
        btn_label = f"✅ {name}" if status else f"❌ {name}"

        # Button click
        if col.button(btn_label, key=name):
            toggle_status(name)
            st.rerun()  # Rerun immediately after click

    st.info("Click on your name to toggle your attendance. Auto-refresh runs every 5 seconds.")

if __name__ == "__main__":
    main()
