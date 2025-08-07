import streamlit as st
import pandas as pd
import zipfile
import re
from datetime import datetime, timedelta
import plotly.graph_objects as go

st.set_page_config(layout="wide")
st.title("Bead Signal Viewer with Machine Status Overlay (Dual Y-Axis, Compressed Time)")

with st.sidebar:
    uploaded_zip = st.file_uploader("Upload ZIP of bead signal CSVs", type="zip")
    status_csv = st.file_uploader("Upload machine status CSV", type="csv")

@st.cache_data
def process_zip(zip_file):
    plots_data = []
    adjusted_time_map = dict()  # maps original_time -> adjusted_time

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

            if plot_rows:
                df_plot = pd.DataFrame(plot_rows)
                df_plot = df_plot.sort_values("original_time").reset_index(drop=True)

                # Compress date gaps
                compressed_times = []
                prev_date = None
                last_end_time = None
                time_offset = timedelta(0)

                for _, row in df_plot.iterrows():
                    current_time = row["original_time"]
                    current_date = row["date"]

                    if prev_date is not None and current_date != prev_date:
                        gap = current_time - last_end_time
                        time_offset += gap

                    compressed_time = current_time - time_offset
                    compressed_times.append(compressed_time)

                    # map original -> adjusted time
                    adjusted_time_map[current_time] = compressed_time

                    prev_date = current_date
                    last_end_time = current_time

                df_plot["adjusted_time"] = compressed_times
                plots_data.append((csv_filename, df_plot))

    return plots_data, adjusted_time_map


def process_status_csv(status_file, adjusted_time_map):
    df_status = pd.read_csv(status_file)
    if not {"Timestamp", "Stat1", "Stat2", "Value"}.issubset(df_status.columns):
        return None, []

    df_status["Timestamp"] = pd.to_datetime(df_status["Timestamp"])
    df_status = df_status[df_status["Timestamp"].isin(adjusted_time_map.keys())].copy()
    df_status["adjusted_time"] = df_status["Timestamp"].map(adjusted_time_map)
    df_status.dropna(subset=["adjusted_time"], inplace=True)

    unique_pairs = df_status[["Stat1", "Stat2"]].dropna().drop_duplicates()
    stat1_options = unique_pairs["Stat1"].unique().tolist()
    return df_status, stat1_options


if uploaded_zip:
    with st.spinner("Processing bead signal ZIP..."):
        plots_data, adjusted_time_map = process_zip(uploaded_zip)

    if not plots_data:
        st.warning("No valid signal CSVs found in ZIP.")
    else:
        # Process status CSV if present
        df_status = None
        selected_stat1 = selected_stat2 = None
        if status_csv:
            with st.spinner("Processing machine status CSV..."):
                df_status, stat1_options = process_status_csv(status_csv, adjusted_time_map)
                if df_status is None or df_status.empty:
                    st.warning("No valid or aligned machine status data found.")
                else:
                    with st.sidebar:
                        selected_stat1 = st.selectbox("Select Stat1", stat1_options)
                        stat2_options = df_status[df_status["Stat1"] == selected_stat1]["Stat2"].unique().tolist()
                        selected_stat2 = st.selectbox("Select Stat2", stat2_options)

                    stat_filtered = df_status[
                        (df_status["Stat1"] == selected_stat1) &
                        (df_status["Stat2"] == selected_stat2)
                    ]

        # Draw figures
        for csv_file_name, df_plot in plots_data:
            st.subheader(f"📄 Plot from file: {csv_file_name}")

            fig = go.Figure()

            # Plot bead lines (left Y-axis)
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

            # Plot machine status line (right Y-axis)
            if status_csv and df_status is not None and not stat_filtered.empty:
                fig.add_trace(go.Scatter(
                    x=stat_filtered["adjusted_time"],
                    y=stat_filtered["Value"],
                    mode="lines+markers",
                    name=f"{selected_stat1}-{selected_stat2}",
                    line=dict(color="firebrick", width=2, dash="dot"),
                    marker=dict(size=4),
                    yaxis="y2",
                    customdata=stat_filtered[["Timestamp"]],
                    hovertemplate=(
                        f"Stat: {selected_stat1}-{selected_stat2}<br>"
                        f"Time: %{{customdata[0]|%Y-%m-%d %H:%M:%S}}<br>"
                        f"Value: %{{y:.2f}}<extra></extra>"
                    )
                ))

            fig.update_layout(
                title=f"Signal per Bead – from {csv_file_name}",
                xaxis_title="Compressed Time (Continuous Data Only)",
                yaxis=dict(title="Signal", side="left"),
                yaxis2=dict(title="Machine Status Value", overlaying="y", side="right"),
                height=500,
                legend_title="Bead / Status",
                hovermode="closest"
            )

            st.plotly_chart(fig, use_container_width=True)
