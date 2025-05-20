import streamlit as st

# Page setup
st.set_page_config(page_title="Team Attendance", layout="centered")
st.title("🔆 Team Attendance Tracker")

# Team members
team_members = [
    "Alice", "Bob", "Charlie", "Diana", "Ethan",
    "Fiona", "George", "Hannah", "Ivy", "Jack"
]

# Session state for attendance
for member in team_members:
    if f"{member}_state" not in st.session_state:
        st.session_state[f"{member}_state"] = False  # OFF by default

# Neon style
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

# Layout in two columns
cols = st.columns(2)

for idx, member in enumerate(team_members):
    col = cols[idx % 2]

    with col:
        # Define state key
        state_key = f"{member}_state"
        click_key = f"{member}_click"

        # Button that triggers a state change
        if st.button(f"{'✅' if st.session_state[state_key] else '❌'} {member}", key=click_key):
            st.session_state[state_key] = not st.session_state[state_key]

        # Show neon-style status
        if st.session_state[state_key]:
            st.markdown(f'<div class="neon-on">{member} is ON</div>', unsafe_allow_html=True)
        else:
            st.markdown(f'<div class="neon-off">{member} is OFF</div>', unsafe_allow_html=True)
