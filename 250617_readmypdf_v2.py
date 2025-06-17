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
You are a helpful assistant.

Given a raw filename, do the following:
1. Guess a clean, human-readable title.
2. Detect if it's in English or Korean.
3. Translate it to the opposite language.
4. Guess what the document is about based only on the file name, and provide the description in both English and Korean.

Respond only in this exact JSON format:
{{
  "title": "cleaned readable title",
  "translated_title": "translated version",
  "brief_description_en": "short summary in English",
  "brief_description_ko": "short summary in Korean"
}}

Filename: {file_name}
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
                        parsed = json.loads(output)
                        pages = next((p["page_count"] for p in pdf_info if p["file_name"] == file_name), "N/A")

                        # Always show both title versions
                        row = {
                            "Original File Name": file_name,
                            "Pages": pages,
                            "English Title": parsed["title"] if parsed["title"].isascii() else parsed["translated_title"],
                            "Korean Title": parsed["translated_title"] if not parsed["translated_title"].isascii() else parsed["title"],
                            "Description (EN)": parsed.get("brief_description_en", ""),
                            "Description (KO)": parsed.get("brief_description_ko", "")
                        }
                        results.append(row)

                        st.markdown(f"""
**Original File Name**: `{row['Original File Name']}`  
**Pages**: {row['Pages']}  
**English Title**: *{row['English Title']}*  
**Korean Title**: *{row['Korean Title']}*  

**📘 Description (EN)**: {row['Description (EN)']}  
**📙 Description (KO)**: {row['Description (KO)']}
""")
                        st.success("✅ Parsed successfully.")
                    except json.JSONDecodeError:
                        st.error("❌ LLM did not return valid JSON.")
                        st.text(output)
                    except Exception as e:
                        st.error("❌ Unexpected error.")
                        st.exception(e)
    if results:
        st.markdown("### 🧾 All Processed Results")
        st.dataframe(pd.DataFrame(results))
