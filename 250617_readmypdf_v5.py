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
        pdf_info.append({"file_name": f, "page_count": pages, "path": os.path.join(temp_dir.name, f)})
    return sorted(pdf_info, key=lambda x: x["file_name"]), non_pdf_files, temp_dir

def build_prompt(file_name):
    return f"""
You are a smart document assistant.

The following string is a PDF file name that may include tags that mostly written inside "[ ]", publication dates, unnecessary symbols, or extra metadata.

Please extract:
1. A clean, human-readable **title** of the paper.
2. Detect the language of the title (Korean or English).
3. Translate the title into the opposite language (Korean ↔ English).
4. Give a summary of what the document might be about and add glossary of technical terms that appeared in the title.

Respond in this exact JSON format:
{{
  "title_en": "cleaned title in English",
  "title_ko": "translated title in Korean",
  "description_en": "brief English description",
  "description_ko": "brief Korean description"
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

    selected_file = st.selectbox("Select PDF file to analyze:", raw_filenames, key="selected_pdf")
    selected_meta = next((p for p in pdf_info if p["file_name"] == selected_file), {})
    pages = selected_meta.get("page_count", "N/A")
    pdf_path = selected_meta.get("path")

    if selected_file and "filename_result" not in st.session_state:
        prompt = build_prompt(selected_file)
        with st.spinner("🔍 Analyzing filename with DeepSeek..."):
            try:
                output = ask_llm(prompt)
                cleaned = output.strip().strip("```json").strip("```").strip()
                parsed = json.loads(cleaned)
                st.session_state.filename_result = {
                    "English Title": parsed.get("title_en", "-"),
                    "Korean Title": parsed.get("title_ko", "-"),
                    "Description (EN)": parsed.get("description_en", "-"),
                    "Description (KO)": parsed.get("description_ko", "-")
                }
                st.success("✅ Filename parsed and translated successfully.")
            except Exception as e:
                st.session_state.filename_result = {
                    "English Title": "❌ Error",
                    "Korean Title": "❌ Error",
                    "Description (EN)": str(e),
                    "Description (KO)": "-"
                }

    if "filename_result" in st.session_state and st.session_state.filename_result is not None:
        st.markdown(f"""
**Original File Name**: `{selected_file}`  
**Pages**: {pages}  
**English Title**: *{st.session_state.filename_result['English Title']}*  
**Korean Title**: *{st.session_state.filename_result['Korean Title']}*  

**📘 Description (EN)**: {st.session_state.filename_result['Description (EN)']}  
**📙 Description (KO)**: {st.session_state.filename_result['Description (KO)']}
""")

    if isinstance(pages, int):
        st.subheader("📄 Page-based Text Analysis")
        selected_page = st.number_input("Select page number to analyze:", min_value=1, max_value=pages, step=1, key="selected_page")

        if "page_text" not in st.session_state or st.session_state.page_from != selected_page:
            try:
                doc = fitz.open(pdf_path)
                page_text = doc.load_page(selected_page - 1).get_text()
                doc.close()
                st.session_state.page_text = page_text
                st.session_state.page_from = selected_page
            except Exception as e:
                st.session_state.page_text = "❌ Failed to extract text from page."
                st.session_state.page_from = selected_page

        st.text_area("Extracted text from selected page:", st.session_state.page_text, height=200)

        prompt_option = st.selectbox("Choose a task for this page:", [
            "Translate to the opposite language (KR ↔ EN)",
            "Summarize in both English and Korean",
            "Extract technical terms",
            "Freeform prompt"
        ], key="selected_task")

        if prompt_option == "Freeform prompt":
            user_prompt = st.text_area("Enter your own prompt:", key="custom_prompt")
        else:
            user_prompt = f"{prompt_option}: {st.session_state.page_text}"

        if st.button("Run LLM Analysis") and user_prompt.strip():
            with st.spinner("🧠 Sending selected page to LLM..."):
                try:
                    result = ask_llm(user_prompt)
                    st.markdown("### 🧾 LLM Output:")
                    st.write(result)
                except Exception as e:
                    st.error("❌ LLM call failed.")
                    st.exception(e)

    # Reset filename analysis when changing file
    if st.session_state.get("_selected_file") != selected_file:
        st.session_state.filename_result = None
        st.session_state.page_text = ""
        st.session_state.page_from = None
        st.session_state._selected_file = selected_file
