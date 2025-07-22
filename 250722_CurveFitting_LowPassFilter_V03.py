import streamlit as st
import pandas as pd
import numpy as np
import plotly.graph_objects as go
from scipy.signal import butter, filtfilt, savgol_filter

st.set_page_config(page_title="NIR/VIS Curve Fitting vs Low-pass Filter Dashboard", layout="wide")

st.title("NIR / VIS Curve Fitting vs Low-pass Filter Comparison Dashboard")

# File Upload in Sidebar
with st.sidebar:
    uploaded_file = st.file_uploader("Upload a CSV file", type="csv")

@st.cache_data
def load_csv(file):
    return pd.read_csv(file)

@st.cache_data
def curve_fitting(input_array, interval):
    m_input = input_array.copy()
    m_re = np.zeros_like(m_input)
    if interval % 2 != 0:
        interval += 1
    m_half = interval // 2
    for i in range(len(m_input)):
        if i < m_half:
            if i == 0:
                m_re[i] = m_input[i]
            else:
                m_re[i] = np.mean(m_input[:i + i + 1])
        elif i >= len(m_input) - m_half:
            m_re[i] = np.mean(m_input[i - ((len(m_input) - i) - 1): i + ((len(m_input) - i))])
        else:
            if i == m_half:
                m_re[i] = np.mean(m_input[i - m_half: i + m_half + 1])
            else:
                m_re[i] = m_re[i - 1] + (m_input[i + m_half] - m_input[i - m_half - 1]) / (interval + 1)
    return m_re

def moving_average(input_array, window_size):
    return np.convolve(input_array, np.ones(window_size)/window_size, mode='same')

def butter_lowpass_filter(data, cutoff, fs, order):
    nyq = 0.5 * fs
    normal_cutoff = cutoff / nyq
    b, a = butter(order, normal_cutoff, btype='low', analog=False)
    return filtfilt(b, a, data)

def segment_beads(df, column, threshold):
    start_indices, end_indices = [], []
    signal = df[column].to_numpy()
    i = 0
    while i < len(signal):
        if signal[i] > threshold:
            start = i
            while i < len(signal) and signal[i] > threshold:
                i += 1
            end = i - 1
            start_indices.append(start)
            end_indices.append(end)
        else:
            i += 1
    return list(zip(start_indices, end_indices))

if uploaded_file is not None:
    df = load_csv(uploaded_file)
    st.write("Data Preview:", df.head())

    if "beads" not in st.session_state:
        with st.sidebar:
            column = st.selectbox("Select filter column for bead segmentation:", df.columns)
            threshold = st.number_input("Enter threshold for bead segmentation:", value=0.0)
            if st.button("Segment Beads"):
                st.session_state.beads = segment_beads(df, column, threshold)
                st.session_state.column = column
                st.session_state.segmented = True

    if "beads" in st.session_state:
        beads = st.session_state.beads
        column = st.session_state.column

        bead_options = [str(i+1) for i in range(len(beads))]

        with st.sidebar:
            selected_bead_idx = st.selectbox("Select Bead Number to Display", bead_options, index=0)
            selected_bead_idx = int(selected_bead_idx) - 1
            interval = st.slider("Curve Fitting Interval", 3, 101, 15, step=2)
            filter_type = st.selectbox("Low-pass Filter Type", ["Butterworth", "Moving Average", "Savitzky-Golay"])
            
            if filter_type == "Butterworth":
                cutoff = st.slider("Cutoff Frequency", 0.01, 0.49, 0.1)
                order = st.slider("Filter Order", 1, 10, 3)
            elif filter_type == "Moving Average":
                ma_window = st.slider("Moving Average Window", 3, 101, 15, step=2)
            elif filter_type == "Savitzky-Golay":
                sg_window = st.slider("Savgol Window Length", 3, 101, 15, step=2)
                sg_polyorder = st.slider("Savgol Polyorder", 1, 10, 3)

        # Precompute filtered signals for all beads
        bead_results = []
        for start, end in beads:
            bead_df = df.iloc[start:end + 1]
            nir = bead_df.iloc[:, 0].to_numpy()
            vis = bead_df.iloc[:, 1].to_numpy()

            nir_curve = curve_fitting(nir, interval)
            vis_curve = curve_fitting(vis, interval)

            if filter_type == "Butterworth":
                nir_filter = butter_lowpass_filter(nir, cutoff, fs=1.0, order=order)
                vis_filter = butter_lowpass_filter(vis, cutoff, fs=1.0, order=order)
            elif filter_type == "Moving Average":
                nir_filter = moving_average(nir, ma_window)
                vis_filter = moving_average(vis, ma_window)
            elif filter_type == "Savitzky-Golay":
                sg_window = sg_window if sg_window % 2 else sg_window + 1
                nir_filter = savgol_filter(nir, window_length=sg_window, polyorder=sg_polyorder)
                vis_filter = savgol_filter(vis, window_length=sg_window, polyorder=sg_polyorder)

            bead_results.append({"nir_raw": nir, "vis_raw": vis, "nir_curve": nir_curve, "vis_curve": vis_curve, "nir_filter": nir_filter, "vis_filter": vis_filter})

        # Display plots for selected bead only
        selected_data = bead_results[selected_bead_idx]

        for idx, signal_label in enumerate(["nir", "vis"]):
            raw = selected_data[f"{signal_label}_raw"]
            curve = selected_data[f"{signal_label}_curve"]
            filtered = selected_data[f"{signal_label}_filter"]

            fig = go.Figure()
            fig.add_trace(go.Scatter(y=raw, name="Raw"))
            fig.add_trace(go.Scatter(y=curve, name="Curve Fitting"))
            fig.add_trace(go.Scatter(y=filtered, name=f"{filter_type} Filter"))
            st.subheader(f"{'NIR' if idx == 0 else 'VIS'} - Bead {selected_bead_idx + 1}")
            st.plotly_chart(fig, use_container_width=True)

else:
    st.info("Please upload a CSV file to begin.")
