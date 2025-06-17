import streamlit as st
import zipfile
import tempfile
import os
import fitz  # PyMuPDF
import requests
import pandas as pd
import json

# Together.ai API setup
TOGETHER_API_KEY = st.secrets["together"]["api_key"]
TOGETHER_URL = "https://api.together.xyz/v1/chat/completions"
MODEL = "meta-llama/Meta-Llama-3.1-8B-Instruct-Turbo"

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
Given a file name: {file_name}

1. Guess a clean, human-readable title.
2. Detect the language (English or Korean) and translate it to the other.
3. Guess briefly what this document might be about.

Respond in JSON format:
{{
  "title": "...",
  "translated_title": "...",
  "brief_description": "..."
}}
"""

def ask_together(prompt):
    headers = {
        "Authorization": f"Bearer {TOGETHER_API_KEY}",
        "Content-Type": "application/json"
    }
    payload = {
        "model": MODEL,
        "messages": [{"role": "user", "content": prompt}],
        "temperature": 0.7,
        "max_tokens": 512
    }
    response = requests.post(TOGETHER_URL, headers=headers, json=payload)
    response.raise_for_status()
    return response.json()["choices"][0]["message"]["content"]

# Streamlit UI
st.set_page_config(page_title="PDF Filename Explainer", layout="centered")
st.sidebar.title("📦 Upload ZIP with PDFs")
uploaded_zip = st.sidebar.file_uploader("Upload a ZIP file", type="zip")

if uploaded_zip:
    pdf_info, non_pdf_files, temp_dir = extract_pdfs(uploaded_zip)
    raw_filenames = [pdf["file_name"] for pdf in pdf_info]
    st.success(f"✅ Found {len(raw_filenames)} PDF file(s).")
    if non_pdf_files:
        st.warning(f"⚠️ {len(non_pdf_files)} non-PDF file(s) detected. This app only supports PDFs.")

    select_all = st.checkbox("Select all files")
    selected_files = raw_filenames if select_all else st.multiselect("Select PDF files to analyze:", raw_filenames)

    results = []
    for file_name in selected_files:
        with st.expander(f"📄 {file_name}"):
            prompt = build_prompt(file_name)
            st.code(prompt.strip(), language="text")
            if st.button("Explain this file name", key=f"explain_{file_name}"):
                with st.spinner("🔍 Analyzing with Together.ai..."):
                    try:
                        output = ask_together(prompt)
                        st.code(output, language="json")
                        parsed = json.loads(output)
                        row = {
                            "Original File Name": file_name,
                            "Pages": next((p["page_count"] for p in pdf_info if p["file_name"] == file_name), "N/A"),
                            "English Title": parsed["title"] if parsed["title"].isascii() else parsed["translated_title"],
                            "Korean Title": parsed["translated_title"] if not parsed["translated_title"].isascii() else parsed["title"],
                            "Description": parsed["brief_description"]
                        }
                        results.append(row)
                        st.success("✅ Parsed successfully.")
                        st.dataframe(pd.DataFrame([row]))
                    except json.JSONDecodeError:
                        st.error("❌ LLM did not return valid JSON.")
                        st.text(output)
                    except Exception as e:
                        st.error("❌ Unexpected error.")
                        st.exception(e)
    if results:
        st.markdown("### 🧾 All Processed Results")
        st.dataframe(pd.DataFrame(results))
