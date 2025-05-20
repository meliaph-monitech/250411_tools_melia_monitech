import streamlit as st

# Set page config
st.set_page_config(page_title="Team Attendance", layout="centered")
st.title("🔆 Team Attendance Tracker")

# Team members
team_members = [
    "Alice", "Bob", "Charlie", "Diana", "Ethan",
    "Fiona", "George", "Hannah", "Ivy", "Jack"
]

# Initialize states
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

# Layout
cols = st.columns(2)

for idx, member in enumerate(team_members):
    col = cols[idx % 2]
    with col:
        # Show the correct button label based on current state
        current_state = st.session_state[member]
        button_label = f"{'✅' if current_state else '❌'} {member}"

        # Button click toggles state
        if st.button(button_label, key=f"btn_{member}"):
            st.session_state[member] = not current_state
            current_state = not current_state  # Update immediately

        # Show neon status
        status_class = "neon-on" if current_state else "neon-off"
        status_text = "ON" if current_state else "OFF"
        st.markdown(f'<div class="{status_class}">{member} is {status_text}</div>', unsafe_allow_html=True)
