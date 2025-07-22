import streamlit as st
import pandas as pd
import numpy as np
import plotly.graph_objects as go
from scipy.signal import butter, filtfilt, savgol_filter

st.set_page_config(page_title="NIR/VIS Curve Fitting vs Low-pass Filter Dashboard", layout="wide")

st.title("NIR / VIS Curve Fitting vs Low-pass Filter Comparison Dashboard")

# File Upload
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

    with st.sidebar:
        column = st.selectbox("Select filter column for bead segmentation:", df.columns)
        threshold = st.number_input("Enter threshold for bead segmentation:", value=0.0)
        segment_button = st.button("Segment Beads")

    if segment_button:
        beads = segment_beads(df, column, threshold)
        bead_options = list(range(len(beads)))

        with st.sidebar:
            selected_bead = st.selectbox("Select Bead Number", bead_options)
            interval = st.slider("Curve Fitting Interval", 3, 101, 15, step=2)
            filter_type = st.selectbox("Low-pass Filter Type", ["Butterworth", "Moving Average", "Savitzky-Golay"])
            cutoff = st.slider("Butterworth Cutoff Frequency", 0.01, 0.49, 0.1)
            order = st.slider("Butterworth/Savgol Order", 1, 10, 3)
            ma_window = st.slider("Moving Average Window", 3, 101, 15, step=2)

        start, end = beads[selected_bead]
        bead_df = df.iloc[start:end + 1]

        for idx in [0, 1]:
            signal = bead_df.iloc[:, idx].to_numpy()
            curve = curve_fitting(signal, interval)

            if filter_type == "Butterworth":
                filtered = butter_lowpass_filter(signal, cutoff, fs=1.0, order=order)
            elif filter_type == "Moving Average":
                filtered = moving_average(signal, ma_window)
            elif filter_type == "Savitzky-Golay":
                filtered = savgol_filter(signal, window_length=ma_window if ma_window % 2 else ma_window+1, polyorder=order)

            fig = go.Figure()
            fig.add_trace(go.Scatter(y=signal, name="Raw"))
            fig.add_trace(go.Scatter(y=curve, name="Curve Fitting"))
            fig.add_trace(go.Scatter(y=filtered, name=f"{filter_type} Filter"))
            st.subheader(f"Column {idx}: {'NIR' if idx == 0 else 'VIS'}")
            st.plotly_chart(fig, use_container_width=True)

    else:
        st.info("Choose column, threshold and click Segment Beads to continue.")
