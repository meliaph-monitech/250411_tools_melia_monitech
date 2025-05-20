import streamlit as st

# Set page config
st.set_page_config(page_title="Attendance Display", layout="wide")

# Define the names for the 12 people
names = [
    "Alice", "Bob", "Charlie", "Diana",
    "Eve", "Frank", "Grace", "Hank",
    "Ivy", "Jack", "Kathy", "Leo"
]

# Initialize session state to track the status of each person
if "statuses" not in st.session_state:
    st.session_state.statuses = [False] * len(names)

# CSS for neon button styling
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

for idx, name in enumerate(names):
    # Determine the button class based on the status
    button_class = "neon-button on" if st.session_state.statuses[idx] else "neon-button off"

    # Create a button with the neon effect
    if st.button(name, key=f"btn_{idx}", help=f"Toggle {name}"):
        # Toggle the status
        st.session_state.statuses[idx] = not st.session_state.statuses[idx]

    # Add the button with dynamic classes
    st.markdown(
        f"""
        <button class="{button_class}" onclick="document.querySelector('[data-testid=btn_{idx}]').click()">
            {name}
        </button>
        """,
        unsafe_allow_html=True,
    )

st.markdown("</div>", unsafe_allow_html=True)
