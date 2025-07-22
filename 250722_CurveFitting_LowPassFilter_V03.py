import streamlit as st
import pandas as pd
import numpy as np
import plotly.graph_objects as go
from scipy.signal import butter, filtfilt, savgol_filter, cheby1, ellip, medfilt
from scipy.ndimage import gaussian_filter1d

st.set_page_config(page_title="NIR/VIS Curve Fitting vs Low-pass Filter Dashboard", layout="wide")

st.title("NIR / VIS Curve Fitting vs Low-pass Filter Comparison Dashboard")

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

def chebyshev_filter(data, cutoff, fs, order, ripple):
    nyq = 0.5 * fs
    normal_cutoff = cutoff / nyq
    b, a = cheby1(order, ripple, normal_cutoff, btype='low', analog=False)
    return filtfilt(b, a, data)

def elliptic_filter(data, cutoff, fs, order, ripple, stopband):
    nyq = 0.5 * fs
    normal_cutoff = cutoff / nyq
    b, a = ellip(order, ripple, stopband, normal_cutoff, btype='low', analog=False)
    return filtfilt(b, a, data)

def gaussian_filter(data, sigma):
    return gaussian_filter1d(data, sigma)

def exponential_moving_average(data, alpha):
    ema = np.zeros_like(data)
    ema[0] = data[0]
    for i in range(1, len(data)):
        ema[i] = alpha * data[i] + (1 - alpha) * ema[i - 1]
    return ema

def median_filter(data, kernel_size):
    return medfilt(data, kernel_size=kernel_size)

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
    # st.write("Data Preview:", df.head())

    if "beads" not in st.session_state:
        with st.sidebar:
            column = st.selectbox("Select filter column for bead segmentation:", df.columns)
            threshold = st.number_input("Enter threshold for bead segmentation:", value=0.0)
            if st.button("Segment Beads"):
                st.session_state.beads = segment_beads(df, column, threshold)
                st.session_state.column = column

    if "beads" in st.session_state:
        beads = st.session_state.beads

        bead_options = [str(i+1) for i in range(len(beads))]

        with st.sidebar:
            selected_bead_idx = st.selectbox("Select Bead Number to Display", bead_options, index=0)
            selected_bead_idx = int(selected_bead_idx) - 1
            interval = st.slider("Curve Fitting Interval", 3, 101, 15, step=2)
            filter_type = st.selectbox("Low-pass Filter Type", ["Butterworth", "Moving Average", "Savitzky-Golay", "Gaussian", "Chebyshev", "Elliptic", "Exponential MA", "Median"])

            if filter_type == "Butterworth":
                cutoff = st.slider("Cutoff Frequency", 0.01, 0.49, 0.1)
                order = st.slider("Filter Order", 1, 10, 3)
            elif filter_type == "Moving Average":
                ma_window = st.slider("Window Size", 3, 101, 15, step=2)
            elif filter_type == "Savitzky-Golay":
                sg_window = st.slider("Window Length", 3, 101, 15, step=2)
                sg_polyorder = st.slider("Polynomial Order", 1, 10, 3)
            elif filter_type == "Gaussian":
                sigma = st.slider("Sigma", 0.1, 10.0, 2.0)
            elif filter_type == "Chebyshev":
                cutoff = st.slider("Cutoff Frequency", 0.01, 0.49, 0.1)
                order = st.slider("Order", 1, 10, 3)
                ripple = st.slider("Ripple (dB)", 0.1, 5.0, 1.0)
            elif filter_type == "Elliptic":
                cutoff = st.slider("Cutoff Frequency", 0.01, 0.49, 0.1)
                order = st.slider("Order", 1, 10, 3)
                ripple = st.slider("Passband Ripple (dB)", 0.1, 5.0, 1.0)
                stopband = st.slider("Stopband Attenuation (dB)", 10.0, 60.0, 40.0)
            elif filter_type == "Exponential MA":
                alpha = st.slider("Alpha (Smoothing Factor)", 0.01, 1.0, 0.1)
            elif filter_type == "Median":
                kernel_size = st.slider("Kernel Size", 3, 101, 15, step=2)

        start, end = beads[selected_bead_idx]
        bead_df = df.iloc[start:end + 1]

        for idx, label in enumerate(["nir", "vis"]):
            signal = bead_df.iloc[:, idx].to_numpy()
            curve = curve_fitting(signal, interval)

            if filter_type == "Butterworth":
                filtered = butter_lowpass_filter(signal, cutoff, fs=1.0, order=order)
            elif filter_type == "Moving Average":
                filtered = moving_average(signal, ma_window)
            elif filter_type == "Savitzky-Golay":
                sg_window = sg_window if sg_window % 2 else sg_window + 1
                filtered = savgol_filter(signal, sg_window, sg_polyorder)
            elif filter_type == "Gaussian":
                filtered = gaussian_filter(signal, sigma)
            elif filter_type == "Chebyshev":
                filtered = chebyshev_filter(signal, cutoff, fs=1.0, order=order, ripple=ripple)
            elif filter_type == "Elliptic":
                filtered = elliptic_filter(signal, cutoff, fs=1.0, order=order, ripple=ripple, stopband=stopband)
            elif filter_type == "Exponential MA":
                filtered = exponential_moving_average(signal, alpha)
            elif filter_type == "Median":
                filtered = median_filter(signal, kernel_size)

            fig = go.Figure()
            fig.add_trace(go.Scatter(y=signal, name="Raw", line=dict(color='gray')))
            fig.add_trace(go.Scatter(y=curve, name="Curve Fitting", line=dict(color='blue', dash='dash')))
            fig.add_trace(go.Scatter(y=filtered, name=f"{filter_type} Filter", line=dict(color='red')))
            st.subheader(f"{'NIR' if idx == 0 else 'VIS'} - Bead {selected_bead_idx + 1}")
            st.plotly_chart(fig, use_container_width=True)

else:
    st.info("Please upload a CSV file to begin.")
