import streamlit as st

# Set up the page
st.set_page_config(page_title="Team Attendance", layout="centered")
st.title("🔆 Team Attendance Tracker")

# Define team members
team_members = [
    "Alice", "Bob", "Charlie", "Diana", "Ethan",
    "Fiona", "George", "Hannah", "Ivy", "Jack"
]

# Initialize session state for each member
for member in team_members:
    if member not in st.session_state:
        st.session_state[member] = False

# Neon-style CSS
st.markdown("""
    <style>
    .neon-on {
        background-color: #39ff14;
        color: black;
        font-weight: bold;
        border-radius: 10px;
        padding: 10px 20px;
        text-align: center;
        box-shadow: 0 0 10px #39ff14, 0 0 20px #39ff14, 0 0 30px #39ff14;
        margin-bottom: 10px;
    }
    .neon-off {
        background-color: #222;
        color: white;
        border: 1px solid #444;
        border-radius: 10px;
        padding: 10px 20px;
        text-align: center;
        margin-bottom: 10px;
    }
    </style>
""", unsafe_allow_html=True)

# Create columns for layout
cols = st.columns(2)

# Track button clicks separately
for idx, member in enumerate(team_members):
    col = cols[idx % 2]

    with col:
        clicked = st.button(f"{'✅ ' if st.session_state[member] else '❌ '}{member}", key=f"btn_{member}")
        if clicked:
            st.session_state[member] = not st.session_state[member]

        status_class = "neon-on" if st.session_state[member] else "neon-off"
        status_text = "ON" if st.session_state[member] else "OFF"
        st.markdown(f'<div class="{status_class}">{member} is {status_text}</div>', unsafe_allow_html=True)
