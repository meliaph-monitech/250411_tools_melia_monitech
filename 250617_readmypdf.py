import streamlit as st
import zipfile
import tempfile
import os
import fitz  # PyMuPDF
import openai
import pandas as pd
import json

# Set up OpenAI API securely (via Streamlit Cloud secrets)
openai.api_key = st.secrets["openai"]["api_key"]

# Sidebar: ZIP upload
st.sidebar.title("📦 Upload ZIP with PDFs")
uploaded_zip = st.sidebar.file_uploader("Upload ZIP file", type="zip")

def extract_pdfs(zip_file):
    temp_dir = tempfile.TemporaryDirectory()
    with zipfile.ZipFile(zip_file, 'r') as zip_ref:
        zip_ref.extractall(temp_dir.name)

    all_files = os.listdir(temp_dir.name)
    pdf_files = [f for f in all_files if f.lower().endswith(".pdf")]
    non_pdf_files = [f for f in all_files if not f.lower().endswith(".pdf")]

    pdf_info = []
    for f in pdf_files:
        try:
            doc = fitz.open(os.path.join(temp_dir.name, f))
            pages = doc.page_count
            doc.close()
        except:
            pages = "Unreadable"
        pdf_info.append({"file_name": f, "page_count": pages})

    return sorted(pdf_info, key=lambda x: x["file_name"]), non_pdf_files, temp_dir

def build_prompt(file_name):
    return f"""
You are a helpful assistant for a document organization tool. Given a raw file name from a PDF document, your tasks are:

1. Guess a clean and human-readable title for the document.
2. Detect the language (English or Korean) and translate the title to the other language.
3. Based on the filename alone, briefly guess what the document might be about (1-2 sentences max).

Filename: {file_name}

Respond in this JSON format:
{{
  "title": "<Guessed Title>",
  "translated_title": "<Translated Title>",
  "brief_description": "<Brief description of the document>"
}}
"""

if uploaded_zip:
    pdf_info, non_pdf_files, temp_dir = extract_pdfs(uploaded_zip)
    raw_filenames = [pdf["file_name"] for pdf in pdf_info]

    st.success(f"✅ Found {len(raw_filenames)} PDF file(s).")
    if non_pdf_files:
        st.warning(f"⚠️ {len(non_pdf_files)} non-PDF file(s) detected. This app currently handles PDF only.")

    # Selection
    select_all = st.checkbox("Select all files")
    selected_files = raw_filenames if select_all else st.multiselect("Select PDF files to analyze:", raw_filenames, key="file_selector")

    results = []

    for file_name in selected_files:
        with st.expander(f"📄 {file_name}"):
            prompt = build_prompt(file_name)
            st.code(prompt.strip(), language="text")

            if st.button(f"Explain this file name", key=f"explain_{file_name}"):
                with st.spinner("🔍 Analyzing with GPT..."):
                    try:
                        response = openai.ChatCompletion.create(
                            model="gpt-3.5-turbo",
                            messages=[{"role": "user", "content": prompt}]
                        )
                        parsed = json.loads(response["choices"][0]["message"]["content"])

                        row = {
                            "Original File Name": file_name,
                            "Pages": next((p["page_count"] for p in pdf_info if p["file_name"] == file_name), "N/A"),
                            "English Title": parsed["title"] if parsed["title"].isascii() else parsed["translated_title"],
                            "Korean Title": parsed["translated_title"] if not parsed["translated_title"].isascii() else parsed["title"],
                            "Description": parsed["brief_description"]
                        }
                        results.append(row)
                        st.success("✅ GPT Response parsed successfully.")
                        st.dataframe(pd.DataFrame([row]))
                    except Exception as e:
                        st.error("❌ GPT call or response parsing failed.")
                        st.exception(e)

    # Show combined results
    if results:
        st.markdown("### 🧾 All Processed Results")
        st.dataframe(pd.DataFrame(results))
