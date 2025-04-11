import os
import zipfile
import io
import base64
import numpy as np
import pandas as pd
from scipy.signal import spectrogram
import matplotlib.pyplot as plt
from flask import Flask, request, jsonify, send_file

app = Flask(__name__)

# Constants
EXTRACT_DIR = "extracted_csvs"

# Clean and extract ZIP
def extract_zip(file_stream):
    if os.path.exists(EXTRACT_DIR):
        for file in os.listdir(EXTRACT_DIR):
            os.remove(os.path.join(EXTRACT_DIR, file))
    else:
        os.makedirs(EXTRACT_DIR)
    with zipfile.ZipFile(file_stream, 'r') as zip_ref:
        zip_ref.extractall(EXTRACT_DIR)
    return [os.path.join(EXTRACT_DIR, f) for f in os.listdir(EXTRACT_DIR) if f.endswith(".csv")]

# Segment beads
def segment_beads(df, column_index, threshold):
    signal = df.iloc[:, column_index].to_numpy()
    starts, ends = [], []
    i = 0
    while i < len(signal):
        if signal[i] > threshold:
            start = i
            while i < len(signal) and signal[i] > threshold:
                i += 1
            ends.append(i - 1)
            starts.append(start)
        else:
            i += 1
    return list(zip(starts, ends))

# Spectrogram computation
def compute_spectrogram(data, fs, nperseg, noverlap, nfft):
    f, t, Sxx = spectrogram(data, fs=fs, nperseg=nperseg, noverlap=noverlap, nfft=nfft)
    Sxx_dB = 20 * np.log10(np.abs(Sxx) + np.finfo(float).eps)
    return f, t, Sxx_dB

# Generate Matplotlib figure
def create_plot(f, t, Sxx_dB, target_frequencies):
    fig, ax = plt.subplots(figsize=(8, 6))
    for freq in target_frequencies:
        band = np.where((f >= freq - 5) & (f <= freq + 5))[0]
        if band.size > 0:
            intensity_over_time = np.mean(Sxx_dB[band, :], axis=0)
            ax.plot(t, intensity_over_time, label=f"{freq} Hz")
    ax.set_xlabel("Time (s)")
    ax.set_ylabel("Signal Intensity (dB)")
    ax.legend()
    ax.grid()
    return fig

# Endpoint 1: Return CSV files and column names
@app.route('/get_csv_metadata', methods=['POST'])
def get_csv_metadata():
    if 'file' not in request.files:
        return jsonify({"error": "No file uploaded"}), 400

    uploaded_file = request.files['file']
    if not uploaded_file.filename.endswith('.zip'):
        return jsonify({"error": "Uploaded file is not a ZIP file"}), 400

    try:
        csv_files = extract_zip(uploaded_file.stream)
        file_column_info = []
        for idx, path in enumerate(csv_files):
            df = pd.read_csv(path)
            file_column_info.append({
                "index": idx,
                "filename": os.path.basename(path),
                "columns": df.columns.tolist()
            })
        return jsonify({"files": file_column_info}), 200
    except Exception as e:
        return jsonify({"error": str(e)}), 500

# Endpoint 2: Generate intensity curve and return as image
@app.route('/analyze_intensity_curve', methods=['POST'])
def analyze_intensity_curve():
    form = request.form
    required_fields = ['file', 'selected_file_index', 'filter_column_index', 'threshold',
                       'bead_number', 'data_column_index', 'target_frequencies']
    if any(f not in request.files and f not in form for f in required_fields):
        return jsonify({"error": "Missing one or more required fields"}), 400

    # Default analysis parameters
    fs = 10000
    nperseg = 1024
    division_factor = 4
    overlap_ratio = 0.99
    nfft = 2048

    try:
        uploaded_file = request.files['file']
        selected_file_index = int(form['selected_file_index'])
        filter_column_index = int(form['filter_column_index'])
        threshold = float(form['threshold'])
        bead_number = int(form['bead_number'])
        data_column_index = int(form['data_column_index'])
        target_frequencies = list(map(float, form['target_frequencies'].split(',')))

        csv_paths = extract_zip(uploaded_file.stream)
        if selected_file_index < 0 or selected_file_index >= len(csv_paths):
            return jsonify({"error": "Selected file index is out of range"}), 400

        # Retrieve the file based on index
        selected_file_path = csv_paths[selected_file_index]
        df = pd.read_csv(selected_file_path)

        segments = segment_beads(df, filter_column_index, threshold)
        if bead_number < 1 or bead_number > len(segments):
            return jsonify({"error": "Bead number out of range"}), 400

        start, end = segments[bead_number - 1]
        segment_data = df.iloc[start:end, data_column_index].to_numpy()

        nperseg = min(nperseg, len(segment_data) // division_factor)
        noverlap = int(overlap_ratio * nperseg)
        nfft = min(nfft, 2 ** int(np.ceil(np.log2(nperseg * 2))))

        f, t, Sxx_dB = compute_spectrogram(segment_data, fs, nperseg, noverlap, nfft)

        # Create the intensity plot
        fig = create_plot(f, t, Sxx_dB, target_frequencies)

        # Convert the plot to a base64-encoded image
        img_bytes = io.BytesIO()
        fig.savefig(img_bytes, format='png', bbox_inches='tight')
        img_bytes.seek(0)

        # Encode image as base64 string
        img_base64 = base64.b64encode(img_bytes.read()).decode('utf-8')
        plt.close(fig)

        return jsonify({"image": img_base64}), 200

    except Exception as e:
        return jsonify({"error": str(e)}), 500

if __name__ == "__main__":
    app.run(host="0.0.0.0", port=5000)