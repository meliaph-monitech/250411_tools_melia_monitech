import streamlit as st
import pandas as pd
import zipfile
import re
from datetime import datetime, timedelta
import plotly.graph_objects as go

st.set_page_config(layout="wide")
st.title("Bead Signal + Machine Status Viewer (Dual Axis, Unified Time)")

# --- Sidebar Inputs ---
st.sidebar.header("Upload Files")
uploaded_zip = st.sidebar.file_uploader("Upload ZIP of Bead Signal CSVs", type="zip")
status_csv = st.sidebar.file_uploader("Upload Machine Status CSV", type="csv")

# --- Helper Function ---
@st.cache_data
def process_zip(zip_file):
    plots_data = []
    all_times = []

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
                        "original_time": timestamp,
                        "date": timestamp.date(),
                        "signal": row[i],
                        "bead_number": f"Bead {i:02d}",
                        "csv_name": csv_name,
                        "source_file": csv_filename
                    })
                    all_times.append(timestamp)

            if plot_rows:
                df_plot = pd.DataFrame(plot_rows)
                df_plot = df_plot.sort_values("original_time").reset_index(drop=True)

                # Compress gaps between dates
                compressed_times = []
                prev_date = None
                time_offset = timedelta(0)
                last_end_time = None

                for _, row in df_plot.iterrows():
                    current_time = row["original_time"]
                    current_date = row["date"]

                    if prev_date is not None and current_date != prev_date:
                        gap = current_time - last_end_time
                        time_offset += gap

                    compressed_time = current_time - time_offset
                    compressed_times.append(compressed_time)

                    prev_date = current_date
                    last_end_time = current_time

                df_plot["adjusted_time"] = compressed_times
                plots_data.append((csv_filename, df_plot))

    return plots_data, all_times

# --- Load and Process Status CSV ---
def process_status_csv(status_file):
    df_status = pd.read_csv(status_file)
    df_status["Timestamp"] = pd.to_datetime(df_status["Timestamp"])
    return df_status

# --- Main Execution ---
if uploaded_zip:
    with st.spinner("Processing bead signal ZIP file..."):
        plots_data, all_bead_times = process_zip(uploaded_zip)

    if not plots_data:
        st.warning("No valid CSV data found in ZIP.")
    else:
        if status_csv:
            df_status = process_status_csv(status_csv)
            stat1_options = df_status["Stat1"].dropna().unique().tolist()
            selected_stat1 = st.sidebar.selectbox("Select Stat1", stat1_options)

            stat2_options = df_status[df_status["Stat1"] == selected_stat1]["Stat2"].dropna().unique().tolist()
            selected_stat2 = st.sidebar.selectbox("Select Stat2", stat2_options)

            df_status_filtered = df_status[
                (df_status["Stat1"] == selected_stat1) &
                (df_status["Stat2"] == selected_stat2)
            ].copy()
        else:
            df_status_filtered = None

        min_time = min(all_bead_times)
        max_time = max(all_bead_times)

        for csv_file_name, df_plot in plots_data:
            st.subheader(f"📄 Plot from file: {csv_file_name}")

            fig = go.Figure()

            # Plot status line first (send to back)
            if df_status_filtered is not None and not df_status_filtered.empty:
                fig.add_trace(go.Scatter(
                    x=df_status_filtered["Timestamp"],
                    y=df_status_filtered["Value"],
                    mode="lines",
                    name=f"Status: {selected_stat1}-{selected_stat2}",
                    line=dict(width=2, dash="dot", color="rgba(100,100,100,0.2)"),
                    yaxis="y2",
                    hovertemplate="Time: %{x|%Y-%m-%d %H:%M:%S}<br>Status Value: %{y}<extra></extra>",
                    opacity=0.8
                ))

            for bead in df_plot["bead_number"].unique():
                sub = df_plot[df_plot["bead_number"] == bead]
                fig.add_trace(go.Scatter(
                    x=sub["adjusted_time"],
                    y=sub["signal"],
                    mode="lines",
                    name=bead,
                    line=dict(width=1),
                    customdata=sub[["csv_name", "original_time"]],
                    hovertemplate=(
                        f"Bead: {bead}<br>"
                        f"Original Time: %{{customdata[1]|%Y-%m-%d %H:%M:%S}}<br>"
                        f"Signal: %{{y:.2f}}<br>"
                        f"File: %{{customdata[0]}}<extra></extra>"
                    ),
                    yaxis="y1"
                ))

            fig.update_layout(
                title=f"Signal per Bead – from {csv_file_name}",
                xaxis_title="Time (ZIP only)",
                yaxis=dict(title="Signal", side="left"),
                yaxis2=dict(title="Status Value", overlaying="y", side="right"),
                xaxis=dict(range=[min_time, max_time]),
                height=500,
                legend_title="Bead / Status",
                hovermode="closest"
            )

            st.plotly_chart(fig, use_container_width=True)
