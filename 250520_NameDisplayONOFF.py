import streamlit as st

# Set page configuration
st.set_page_config(page_title="Attendance Display", layout="wide")

# Names for the 12 people
names = [
    "Alice", "Bob", "Charlie", "Diana",
    "Eve", "Frank", "Grace", "Hank",
    "Ivy", "Jack", "Kathy", "Leo"
]

# Initialize session state to track attendance (True = in the room, False = not in the room)
if "statuses" not in st.session_state:
    st.session_state.statuses = [False] * len(names)

# CSS for the neon button
st.markdown(
    """
    <style>
    .grid-container {
        display: grid;
        grid-template-columns: repeat(4, 1fr);
        gap: 10px;
        padding: 20px;
    }
    .neon-button {
        font-size: 20px;
        font-weight: bold;
        color: white;
        text-align: center;
        padding: 15px;
        border: none;
        border-radius: 10px;
        cursor: pointer;
        transition: all 0.3s ease-in-out;
    }
    .neon-button.off {
        background: #444;
        box-shadow: none;
    }
    .neon-button.on {
        background: #00ff00;
        box-shadow: 0 0 10px #00ff00, 0 0 20px #00ff00, 0 0 30px #00ff00;
    }
    </style>
    """,
    unsafe_allow_html=True,
)

# Display the grid of buttons
st.markdown('<div class="grid-container">', unsafe_allow_html=True)

# Create buttons for each name in the grid
for idx, name in enumerate(names):
    # Determine CSS class for the button based on attendance status
    button_class = "neon-button on" if st.session_state.statuses[idx] else "neon-button off"

    # Use a button to toggle the status
    clicked = st.button(name, key=f"btn_{idx}")
    
    # If the button is clicked, toggle the status
    if clicked:
        st.session_state.statuses[idx] = not st.session_state.statuses[idx]

    # Render the button with the appropriate class
    st.markdown(
        f"""
        <style>
        div[data-testid="stButton"] > button[data-testid="btn_{idx}"] {{
            width: 100%;
            height: 100%;
            background: inherit;
            color: inherit;
        }}
        </style>
        <button class="{button_class}">
            {name}
        </button>
        """,
        unsafe_allow_html=True,
    )

st.markdown("</div>", unsafe_allow_html=True)
