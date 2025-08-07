import streamlit as st
import pandas as pd
import re
from io import BytesIO
from datetime import datetime
import plotly.express as px
import plotly.graph_objects as go

st.set_page_config(layout="wide")
st.title("Excel Signal Line Plot by Bead Number and Time")

uploaded_file = st.file_uploader("Upload Excel File", type=["xlsx"])

if uploaded_file:
    xls = pd.ExcelFile(uploaded_file)
    sheet_names = xls.sheet_names

    for sheet in sheet_names:
        st.subheader(f"Sheet: {sheet}")
        with st.spinner(f"Processing {sheet}..."):
            df = pd.read_excel(xls, sheet_name=sheet, header=None)

            records = []

            for _, row in df.iterrows():
                csv_name = row[0]

                # Extract hhmmss, YYMMDD, Fxx, stat
                match = re.search(r"(?P<time>\d{6})_(?P<bm>[A-Z0-9]+)_.*?_(?P<f>F\d+)(?:_(?P<stat>[^.]+))?\.csv", csv_name)
                if not match:
                    continue

                hhmmss = match.group("time")
                bma_code = match.group("bm")
                f_code = match.group("f")
                stat = match.group("stat") if match.group("stat") else ""
                
                # Extract YYMMDD from bma_code
                date_match = re.search(r"(\d{6})Y\d{4}", bma_code)
                yymmdd = date_match.group(1) if date_match else "000000"
                dt_string = yymmdd + hhmmss
                try:
                    dt = datetime.strptime(dt_string, "%y%m%d%H%M%S")
                except:
                    continue

                # Get signal values from bead 1 onward
                for i, value in enumerate(row[1:], start=1):
                    records.append({
                        "timestamp": dt,
                        "csv_name": csv_name,
                        "bead_number": f"Bead {i:02d}",
                        "signal": value
                    })

            # Convert to DataFrame
            if not records:
                st.warning("No valid data found in this sheet.")
                continue

            data = pd.DataFrame(records)

            # Pivot for line plot
            fig = px.line(
                data,
                x="timestamp",
                y="signal",
                color="bead_number",
                line_group="csv_name",
                hover_data={
                    "csv_name": True,
                    "signal": True,
                    "bead_number": True,
                    "timestamp": False,
                },
                labels={"signal": "Signal", "timestamp": "Time", "bead_number": "Bead"},
                title=f"Signal Over Time (Sheet: {sheet})"
            )

            fig.update_layout(height=500, legend_title_text='Bead Number')
            st.plotly_chart(fig, use_container_width=True)
