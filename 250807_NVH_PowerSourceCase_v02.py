import streamlit as st
import pandas as pd
import zipfile
import re
from datetime import datetime
import plotly.graph_objects as go

st.set_page_config(layout="wide")
st.title("Bead Signal Viewer – One Plot per Uploaded CSV File")

uploaded_zip = st.file_uploader("Upload ZIP of CSVs", type="zip")

@st.cache_data
def process_zip(zip_file):
    plots_data = []

    with zipfile.ZipFile(zip_file) as z:
        for csv_filename in sorted(z.namelist()):
            if not csv_filename.lower().endswith(".csv"):
                continue

            with z.open(csv_filename) as f:
                df = pd.read_csv(f, header=None)

            plot_rows = []
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

                for i in range(1, len(row)):
                    plot_rows.append({
                        "timestamp": timestamp,
                        "signal": row[i],
                        "bead_number": f"Bead {i:02d}",
                        "csv_name": csv_name,
                        "source_file": csv_filename
                    })

            if plot_rows:
                df_plot = pd.DataFrame(plot_rows)
                plots_data.append((csv_filename, df_plot))

    return plots_data

if uploaded_zip:
    with st.spinner("Processing uploaded CSVs..."):
        plots_data = process_zip(uploaded_zip)

    if not plots_data:
        st.warning("No valid CSV data found.")
    else:
        for csv_file_name, df_plot in plots_data:
            st.subheader(f"📄 Plot from file: {csv_file_name}")

            fig = go.Figure()

            # Plot each bead with gap handling
            for bead in df_plot["bead_number"].unique():
                sub = df_plot[df_plot["bead_number"] == bead].sort_values("timestamp")

                # Insert None where time jump > 2x median delta (adaptive)
                sub = sub.reset_index(drop=True)
                sub["time_diff"] = sub["timestamp"].diff().dt.total_seconds()

                if len(sub) >= 3:
                    median_diff = sub["time_diff"].median()
                    gap_threshold = median_diff * 2 if pd.notna(median_diff) else 10
                else:
                    gap_threshold = 10  # default 10s

                xs, ys, cds = [], [], []
                for i, row in sub.iterrows():
                    if i > 0 and row["time_diff"] > gap_threshold:
                        xs.append(None)
                        ys.append(None)
                        cds.append(None)
                    xs.append(row["timestamp"])
                    ys.append(row["signal"])
                    cds.append(row["csv_name"])

                fig.add_trace(go.Scatter(
                    x=xs,
                    y=ys,
                    mode="lines",
                    name=bead,
                    line=dict(width=1),
                    customdata=cds,
                    hovertemplate=(
                        f"Bead: {bead}<br>"
                        f"Time: %{{x|%Y-%m-%d %H:%M:%S}}<br>"
                        f"Signal: %{{y:.2f}}<br>"
                        f"File: %{{customdata}}<extra></extra>"
                    )
                ))

            fig.update_layout(
                title=f"Signal per Bead – from {csv_file_name}",
                xaxis_title="Time",
                yaxis_title="Signal",
                height=500,
                legend_title="Bead",
                hovermode="x unified"
            )
            st.plotly_chart(fig, use_container_width=True)
