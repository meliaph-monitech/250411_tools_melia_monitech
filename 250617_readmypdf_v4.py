import streamlit as st
import zipfile
import tempfile
import os
import fitz  # PyMuPDF
import requests
import pandas as pd
import json

# OpenRouter (DeepSeek) API
OPENROUTER_API_KEY = st.secrets["openrouter"]["api_key"]
OPENROUTER_URL = "https://openrouter.ai/api/v1/chat/completions"
MODEL = "deepseek/deepseek-chat-v3-0324:free"

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

# def build_prompt(file_name):
#     return f"""
# You are a smart document assistant.

# The following string is a PDF file name that may include tags that mostly written inside "[ ]", publication dates, unnecessary symbols, or extra metadata.

# Please extract:
# 1. A clean, human-readable **title** of the paper.
# 2. Detect the language of the title (Korean or English).
# 3. Translate the title into the opposite language (Korean ↔ English).
# 4. Give a summary of what the document might be about and add glossary of technical terms that appeared in the title.

# Respond in this exact JSON format:
# {{
#   "title_en": "cleaned title in English",
#   "title_ko": "translated title in Korean",
#   "description_en": "brief English description",
#   "description_ko": "brief Korean description"
# }}

# Filename: {file_name}
# """

def build_prompt(file_name):
    return f"""
You are a smart document assistant.

The following string is a PDF file name that may include tags (like [학회논문]), publication dates, or extra metadata.

Please extract:
1. A clean, human-readable title of the paper.
2. Detect the language of the title (Korean or English).
3. Translate the title into the opposite language (Korean ↔ English).
4. Provide a summary of what the document might be about.
5. Break down the final assumed title word-by-word as a vocabulary list but only include terms that are technical, uncommon, or context-specific — skip generic or well-known words. For each word, include:
   - English word (or romanized Korean)
   - Korean translation
   - A simple English definition
   - A simple Korean definition

Respond in this exact JSON format:
{{
  "title_en": "cleaned title in English",
  "title_ko": "translated title in Korean",
  "description_en": "brief English description",
  "description_ko": "brief Korean description",
  "vocabulary": [
    {{
      "word": "...",
      "korean": "...",
      "definition_en": "...",
      "definition_ko": "..."
    }},
    ...
  ]
}}

Filename: {file_name}
"""


def ask_llm(prompt):
    headers = {
        "Authorization": f"Bearer {OPENROUTER_API_KEY}",
        "Content-Type": "application/json"
    }
    payload = {
        "model": MODEL,
        "messages": [{"role": "user", "content": prompt}],
        "temperature": 0.7,
        "max_tokens": 512
    }
    response = requests.post(OPENROUTER_URL, headers=headers, json=payload)
    response.raise_for_status()
    return response.json()["choices"][0]["message"]["content"]

# Streamlit UI
st.set_page_config(page_title="PDF Filename Explainer", layout="centered")
st.sidebar.title("📆 Upload ZIP with PDFs")
uploaded_zip = st.sidebar.file_uploader("Upload a ZIP file", type="zip")

if uploaded_zip:
    pdf_info, non_pdf_files, temp_dir = extract_pdfs(uploaded_zip)
    raw_filenames = [pdf["file_name"] for pdf in pdf_info]
    st.success(f"✅ Found {len(raw_filenames)} PDF file(s).")
    if non_pdf_files:
        st.warning(f"⚠️ {len(non_pdf_files)} non-PDF file(s) detected. This app only supports PDFs.")

    selected_file = st.selectbox("Select PDF file to analyze:", raw_filenames)

    if selected_file:
        prompt = build_prompt(selected_file)
        # with st.expander(f"📄 {selected_file}"):
        #     st.caption("Prompt sent to LLM (hidden by default):")
        #     st.code(prompt.strip(), language="text")

        with st.spinner("🔍 Analyzing with DeepSeek..."):
            try:
                output = ask_llm(prompt)
                cleaned = output.strip().strip("```json").strip("```").strip()
                parsed = json.loads(cleaned)
                pages = next((p["page_count"] for p in pdf_info if p["file_name"] == selected_file), "N/A")

                row = {
                    "Original File Name": selected_file,
                    "Pages": pages,
                    "English Title": parsed.get("title_en", "-"),
                    "Korean Title": parsed.get("title_ko", "-"),
                    "Description (EN)": parsed.get("description_en", "-"),
                    "Description (KO)": parsed.get("description_ko", "-")
                }

                st.markdown(f"""
**Original File Name**: `{selected_file}`  
**Pages**: {pages}  
**English Title**: *{row['English Title']}*  
**Korean Title**: *{row['Korean Title']}*  

**📘 Description (EN)**: {row['Description (EN)']}  
**📙 Description (KO)**: {row['Description (KO)']}
""")
                st.success("✅ Parsed and translated successfully.")
            except json.JSONDecodeError:
                st.error("❌ LLM did not return valid JSON.")
                st.text(output)
            except Exception as e:
                st.error("❌ Unexpected error.")
                st.exception(e)
