# streamlit_app.py
# Run: streamlit run streamlit_app.py

import streamlit as st
import numpy as np
import pandas as pd

from sklearn.decomposition import PCA
from sklearn.preprocessing import StandardScaler

import plotly.express as px

st.set_page_config(page_title="PCA Explorer (2D/3D) — Plotly", layout="wide")

# =========================================================
# Config
# =========================================================
REQUIRED_COLS = ["Class", "Sub-class", "Stat", "Channel", "Metrics", "Bead", "Value"]

AGG_FUNCS = {
    "mean": "mean",
    "median": "median",
    "min": "min",
    "max": "max",
    "sum": "sum",
}

# =========================================================
# Helpers
# =========================================================
def read_long_table(uploaded_file) -> pd.DataFrame:
    name = uploaded_file.name.lower()
    if name.endswith((".xlsx", ".xls")):
        return pd.read_excel(uploaded_file)
    if name.endswith(".csv"):
        return pd.read_csv(uploaded_file)
    raise ValueError("Unsupported file type. Please upload .csv or .xlsx/.xls")

def add_metric_parts(df: pd.DataFrame) -> pd.DataFrame:
    """
    Metrics examples:
      - SUMP_L, SUMP_U, MAXP_L, MAXP_U
    Adds:
      - MetricFamily: SUMP / MAXP
      - MetricBound : L / U
    """
    out = df.copy()
    m = out["Metrics"].astype(str)
    parts = m.str.split("_", n=1, expand=True)
    out["MetricFamily"] = parts[0]
    out["MetricBound"] = parts[1] if parts.shape[1] > 1 else ""
    return out

def build_feature_name(df: pd.DataFrame, feature_mode: str) -> pd.Series:
    """
    Returns a single string series used as pivot columns.
    """
    if feature_mode == "Metrics (SUMP_L, SUMP_U, MAXP_L, MAXP_U)":
        return df["Metrics"].astype(str)

    if feature_mode == "Group Metrics only (SUMP vs MAXP) [collapse L/U]":
        return df["MetricFamily"].astype(str)

    # "Group + Bound" (SUMP__L, ...)
    return df[["MetricFamily", "MetricBound"]].astype(str).agg("__".join, axis=1)

def pivot_wide(
    df: pd.DataFrame,
    id_cols: list[str],
    feature_mode: str,
    agg: str,
) -> tuple[pd.DataFrame, list[str]]:
    """
    Long -> wide:
      index = id_cols
      columns = feature names (depends on feature_mode)
      values = Value
      aggfunc = agg
    """
    tmp = df.copy()
    tmp["_feature_"] = build_feature_name(tmp, feature_mode)

    wide = (
        tmp.pivot_table(
            index=id_cols,
            columns="_feature_",
            values="Value",
            aggfunc=AGG_FUNCS[agg],
        )
        .reset_index()
    )
    wide.columns.name = None
    feature_cols = [c for c in wide.columns if c not in id_cols]
    return wide, feature_cols

def fit_pca(
    wide: pd.DataFrame,
    id_cols: list[str],
    feature_cols: list[str],
    n_components: int,
    standardize: bool = True,
) -> tuple[pd.DataFrame, np.ndarray]:
    """
    Standardize (optional) -> PCA -> append PC columns.
    NaNs: drop all-NaN rows, fill remaining by column mean.
    """
    X = wide[feature_cols].astype(float)

    # drop rows that have no features at all
    keep = ~X.isna().all(axis=1)
    wide2 = wide.loc[keep].copy()
    X = X.loc[keep].copy()

    if X.shape[0] == 0:
        raise ValueError("After filtering, no rows remain. Check your ID / feature selections.")

    # fill remaining NaNs
    X = X.apply(lambda s: s.fillna(s.mean()), axis=0)

    if X.shape[1] < n_components:
        raise ValueError(
            f"Not enough features ({X.shape[1]}) for PCA({n_components}). "
            f"Try 'Metrics' (4 features) or include more feature detail."
        )

    X_used = StandardScaler().fit_transform(X.values) if standardize else X.values

    pca = PCA(n_components=n_components, random_state=0)
    Z = pca.fit_transform(X_used)
    var = pca.explained_variance_ratio_

    out = wide2.copy()
    out["PC1"] = Z[:, 0]
    out["PC2"] = Z[:, 1]
    if n_components == 3:
        out["PC3"] = Z[:, 2]

    return out, var

def make_plot(
    pca_df: pd.DataFrame,
    dim: str,
    color_by: str,
    hover_cols: list[str],
    title: str,
):
    if dim == "3D":
        fig = px.scatter_3d(
            pca_df,
            x="PC1", y="PC2", z="PC3",
            color=color_by if color_by in pca_df.columns else "Stat",
            hover_data=hover_cols,
            title=title,
        )
        fig.update_traces(marker=dict(size=5))
        return fig

    fig = px.scatter(
        pca_df,
        x="PC1", y="PC2",
        color=color_by if color_by in pca_df.columns else "Stat",
        hover_data=hover_cols,
        title=title,
    )
    fig.update_traces(marker=dict(size=8))
    return fig

# =========================================================
# UI
# =========================================================
st.title("PCA Explorer (2D/3D) — Plotly")
st.caption(
    "Upload your long-format CSV and explore PCA by changing the observation unit (per Channel / Bead / Channel-Bead) "
    "and feature definition (Metrics vs SUMP/MAXP groups), with selectable aggregation."
)

with st.sidebar:
    st.header("1) Upload")
    uploaded = st.file_uploader("Upload CSV (or XLSX)", type=["csv", "xlsx", "xls"])

    st.header("2) Plot Settings")
    dim = st.radio("Plot dimension", ["2D", "3D"], index=1)
    n_components = 3 if dim == "3D" else 2

    st.header("3) Observation unit (point identity)")
    # Base identity always includes Class/Sub-class/Stat
    # Then the user chooses whether to split further.
    unit_mode = st.selectbox(
        "Choose point identity mode",
        [
            "Per item only (Class + Sub-class + Stat)",
            "Per Channel (Class + Sub-class + Stat + Channel)",
            "Per Bead (Class + Sub-class + Stat + Bead)",
            "Per Channel-Bead pair (Class + Sub-class + Stat + Channel + Bead)",
        ],
        index=3,
    )

    st.header("4) Feature definition")
    feature_mode = st.selectbox(
        "Choose feature columns (pivot mode)",
        [
            "Metrics (SUMP_L, SUMP_U, MAXP_L, MAXP_U)",
            "Group Metrics only (SUMP vs MAXP) [collapse L/U]",
            "Group + Bound (SUMP__L, SUMP__U, MAXP__L, MAXP__U)",
        ],
        index=0,
    )

    st.header("5) Aggregation")
    agg = st.selectbox("Aggregate duplicates using", ["mean", "median", "min", "max", "sum"], index=0)

    st.header("6) Preprocess")
    standardize = st.checkbox("Standardize features (recommended)", value=True)

    st.header("7) Color & Hover")
    color_by = st.selectbox("Color points by", ["Stat", "Class", "Channel", "Bead"], index=0)
    show_table = st.checkbox("Show PCA table preview", value=False)

    st.divider()
    start = st.button("▶ Start Plotting", type="primary", use_container_width=True)

if not uploaded:
    st.info("Upload a file to begin. Expected columns: " + ", ".join(REQUIRED_COLS))
    st.stop()

# Load + validate regardless of button click (so we can show errors early)
try:
    df_long = read_long_table(uploaded)
except Exception as e:
    st.error(str(e))
    st.stop()

missing = [c for c in REQUIRED_COLS if c not in df_long.columns]
if missing:
    st.error(f"Missing required columns: {missing}")
    st.stop()

df_long = add_metric_parts(df_long)

# Only compute/plot when the user clicks Start Plotting
if not start:
    st.warning("Set options in the sidebar, then click **Start Plotting**.")
    st.stop()

# Build id columns from unit_mode
id_cols = ["Class", "Sub-class", "Stat"]
if unit_mode.startswith("Per Channel-Bead"):
    id_cols += ["Channel", "Bead"]
elif unit_mode.startswith("Per Channel"):
    id_cols += ["Channel"]
elif unit_mode.startswith("Per Bead"):
    id_cols += ["Bead"]

# Pivot -> PCA
try:
    wide, feature_cols = pivot_wide(df_long, id_cols=id_cols, feature_mode=feature_mode, agg=agg)
    pca_df, var = fit_pca(
        wide,
        id_cols=id_cols,
        feature_cols=feature_cols,
        n_components=n_components,
        standardize=standardize,
    )
except Exception as e:
    st.error(str(e))
    st.stop()

# Build hover columns
hover_cols = [c for c in ["Class", "Sub-class", "Stat", "Channel", "Bead"] if c in pca_df.columns]
# Optionally also show feature values in hover (can get long). Keep it manageable:
# show up to 12 feature columns in hover.
hover_feature_cols = feature_cols[:12]
hover_cols_extended = hover_cols + hover_feature_cols

title = (
    f"{dim} PCA | unit={'+'.join(id_cols)} | features={feature_mode} | agg={agg} | "
    f"explained_var={np.round(var, 3)}"
)

# Layout
left, right = st.columns([2, 1], gap="large")

with left:
    fig = make_plot(
        pca_df,
        dim=dim,
        color_by=color_by,
        hover_cols=hover_cols_extended,
        title=title,
    )
    st.plotly_chart(fig, use_container_width=True)

with right:
    st.subheader("Summary")
    st.write(f"- Points: **{len(pca_df)}**")
    st.write(f"- Features: **{len(feature_cols)}**")
    st.write(f"- Explained variance: **{np.round(var, 4)}**")
    st.write("Feature columns:")
    st.code(", ".join(map(str, feature_cols)))

    if show_table:
        st.subheader("PCA Table (preview)")
        st.dataframe(pca_df.head(80), use_container_width=True)

    st.subheader("Download")
    csv_bytes = pca_df.to_csv(index=False).encode("utf-8")
    st.download_button(
        "Download PCA table as CSV",
        data=csv_bytes,
        file_name="pca_table.csv",
        mime="text/csv",
        use_container_width=True,
    )
