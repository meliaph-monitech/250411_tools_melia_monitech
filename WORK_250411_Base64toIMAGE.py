import streamlit as st
import base64
from io import BytesIO
from PIL import Image

# Streamlit app title
st.title("Base64 to Image Decoder")

# Instructions
st.write(
    """
    This app allows you to decode a Base64 string into an image.
    - Paste the Base64 string below.
    - Click "Decode" to view the image.
    - You can also download the decoded image.
    """
)

# Text input for Base64 string
base64_string = st.text_area("Paste your Base64 string here:", height=200)

# Button to decode the Base64 string
if st.button("Decode"):
    try:
        # Decode the Base64 string
        image_data = base64.b64decode(base64_string)
        # Open the image using PIL
        image = Image.open(BytesIO(image_data))
        
        # Display the image
        st.image(image, caption="Decoded Image", use_column_width=True)
        
        # Create a downloadable link for the image
        buffered = BytesIO()
        image.save(buffered, format="PNG")
        buffered.seek(0)
        b64 = base64.b64encode(buffered.read()).decode()
        href = f'<a href="data:image/png;base64,{b64}" download="decoded_image.png">Download Image</a>'
        
        # Display the download link
        st.markdown(href, unsafe_allow_html=True)

    except Exception as e:
        st.error(f"An error occurred: {e}")
