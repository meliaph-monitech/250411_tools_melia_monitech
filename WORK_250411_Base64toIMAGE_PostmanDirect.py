import streamlit as st
import base64
import json
from io import BytesIO
from PIL import Image

# Streamlit app title
st.title("Base64 to Image Decoder")

# Instructions
st.write(
    """
    This app allows you to decode a Base64 string into an image.
    - Copy and paste the JSON response from Postman (e.g., `{"image": "base64_string"}`).
    - Click "Decode" to view the image.
    - You can also download the decoded image.
    """
)

# Text input for JSON input with a Base64 string
json_input = st.text_area("Paste the JSON response here:", height=200)

# Button to decode the Base64 string
if st.button("Decode"):
    try:
        # Validate input
        if not json_input.strip():
            st.error("Error: The input is empty. Please paste a valid JSON object.")
        else:
            # Parse the JSON input
            parsed_json = json.loads(json_input)

            # Check if the 'image' key exists
            if "image" not in parsed_json:
                st.error("Error: The JSON object must contain an 'image' key.")
            else:
                # Extract the Base64 string from the JSON
                base64_string = parsed_json["image"]

                # Clean and decode the Base64 string
                base64_string_cleaned = base64_string.strip()
                image_data = base64.b64decode(base64_string_cleaned)

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

    except json.JSONDecodeError:
        st.error("Error: Invalid JSON format. Please ensure you paste a valid JSON object.")
    except (base64.binascii.Error, ValueError):
        st.error("Error: The 'image' value is not a valid Base64 string. Please check your input.")
    except Exception as e:
        st.error(f"An unexpected error occurred: {e}")
