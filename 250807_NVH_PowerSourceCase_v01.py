import streamlit as st
import pandas as pd
import zipfile
import re
from datetime import datetime
from io import BytesIO, StringIO
import plotly.express as px

st.set_page_config(layout="wide")
st.title("Bead Signal Line Plot from ZIP of CSV Files")

uploaded_zip = st.file_uploader("Upload ZIP file containing CSVs", type="zip")

@st.cache_data
def load_and_process_zip(zip_file):
    with zipfile.ZipFile(zip_file) as z:
        records = []

        for file_name in z.namelist():
            if not file_name.lower().endswith(".csv"):
                continue

            with z.open(file_name) as f:
                df = pd.read_csv(f, header=None)

            for _, row in df.iterrows():
                csv_name = str(row[0])

                match = re.search(r"(?P<time>\d{6})_(?P<bm>[A-Z0-9]+)_.*?_(?P<f>F\d+)(?:_(?P<stat>[^.]+))?\.csv", csv_name)
                if not match:
                    continue

                hhmmss = match.group("time")
                bma_code = match.group("bm")
                f_code = match.group("f")
                stat = match.group("stat") if match.group("stat") else ""

                # YYMMDD inside BMA
                date_match = re.search(r"(\d{6})Y\d{4}", bma_code)
                yymmdd = date_match.group(1) if date_match else "000000"
                dt_string = yymmdd + hhmmss
                try:
                    timestamp = datetime.strptime(dt_string, "%y%m%d%H%M%S")
                except:
                    continue

                for i in range(1, len(row)):
                    records.append({
                        "timestamp": timestamp,
                        "csv_name": csv_name,
                        "bead_number": f"Bead {i:02d}",
                        "signal": row[i]
                    })

        return pd.DataFrame(records)

if uploaded_zip:
    with st.spinner("Processing uploaded ZIP..."):
        data = load_and_process_zip(uploaded_zip)

    if data.empty:
        st.warning("No valid CSV data found.")
    else:
        st.success(f"Loaded {len(data)} signal records.")

        bead_list = sorted(data["bead_number"].unique())

        fig = px.line(
            data,
            x="timestamp",
            y="signal",
            color="bead_number",
            line_group="csv_name",
            hover_data=["csv_name", "bead_number", "signal"],
            labels={"signal": "Signal", "timestamp": "Time", "bead_number": "Bead"},
            title="Signal Over Time by Bead Number"
        )
        fig.update_layout(height=600, legend_title_text="Bead")
        st.plotly_chart(fig, use_container_width=True)
