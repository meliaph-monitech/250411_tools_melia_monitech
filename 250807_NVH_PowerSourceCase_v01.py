import streamlit as st
import pandas as pd
import zipfile
import re
from datetime import datetime
from io import StringIO
import plotly.graph_objects as go

st.set_page_config(layout="wide")
st.title("Bead Signal Viewer – One Plot per CSV")

uploaded_zip = st.file_uploader("Upload ZIP of CSVs", type="zip")

@st.cache_data
def process_zip(zip_file):
    with zipfile.ZipFile(zip_file) as z:
        plots_data = []

        for file_name in sorted(z.namelist()):
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
                date_match = re.search(r"(\d{6})Y\d{4}", bma_code)
                yymmdd = date_match.group(1) if date_match else "000000"

                try:
                    timestamp = datetime.strptime(yymmdd + hhmmss, "%y%m%d%H%M%S")
                except:
                    continue

                signal_values = row[1:].values
                bead_numbers = [f"Bead {i+1:02d}" for i in range(len(signal_values))]

                df_plot = pd.DataFrame({
                    "timestamp": [timestamp] * len(signal_values),
                    "signal": signal_values,
                    "bead_number": bead_numbers,
                    "csv_name": csv_name
                })

                plots_data.append((csv_name, df_plot))

        return plots_data

if uploaded_zip:
    with st.spinner("Processing CSV files..."):
        plots_data = process_zip(uploaded_zip)

    if not plots_data:
        st.warning("No valid CSV data found.")
    else:
        for csv_name, df_plot in plots_data:
            st.subheader(f"📄 {csv_name}")

            fig = go.Figure()
            for bead in df_plot["bead_number"].unique():
                sub = df_plot[df_plot["bead_number"] == bead]
                fig.add_trace(go.Scatter(
                    x=sub["timestamp"],
                    y=sub["signal"],
                    mode="lines+markers",
                    name=bead,
                    hovertemplate=(
                        f"Bead: {bead}<br>"
                        f"Time: %{{x|%Y-%m-%d %H:%M:%S}}<br>"
                        f"Signal: %{{y:.2f}}<br>"
                        f"File: {csv_name}<extra></extra>"
                    )
                ))

            fig.update_layout(
                title=f"Signal per Bead – {csv_name}",
                xaxis_title="Time",
                yaxis_title="Signal",
                height=500,
                legend_title="Bead"
            )
            st.plotly_chart(fig, use_container_width=True)
