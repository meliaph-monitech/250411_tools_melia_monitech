# streamlit_app.py
# Run: streamlit run streamlit_app.py

import streamlit as st
import numpy as np
import pandas as pd

from sklearn.decomposition import PCA
from sklearn.preprocessing import StandardScaler

import plotly.express as px

st.set_page_config(page_title="PCA Explorer (2D/3D) — Plotly", layout="wide")

REQUIRED_COLS = ["Class", "Sub-class", "Stat", "Channel", "Metrics", "Bead", "Value"]
AGG_FUNCS = {"mean": "mean", "median": "median", "min": "min", "max": "max", "sum": "sum"}

# =========================
# Helpers
# =========================
def read_long_table(uploaded_file) -> pd.DataFrame:
    name = uploaded_file.name.lower()
    if name.endswith((".xlsx", ".xls")):
        return pd.read_excel(uploaded_file)
    if name.endswith(".csv"):
        return pd.read_csv(uploaded_file)
    raise ValueError("Unsupported file type. Please upload .csv or .xlsx/.xls")

def add_metric_parts(df: pd.DataFrame) -> pd.DataFrame:
    """
    Metrics expected like: SUMP_L, SUMP_U, MAXP_L, MAXP_U
    """
    out = df.copy()
    parts = out["Metrics"].astype(str).str.split("_", n=1, expand=True)
    out["MetricFamily"] = parts[0]
    out["MetricBound"] = parts[1] if parts.shape[1] > 1 else ""
    return out

def filter_by_bound(df: pd.DataFrame, bound_mode: str) -> pd.DataFrame:
    """
    bound_mode: "Both (Upper + Lower)" | "Upper only (_U)" | "Lower only (_L)"
    """
    if bound_mode.startswith("Both"):
        return df
    if bound_mode.startswith("Upper"):
        return df[df["MetricBound"].astype(str).str.upper().eq("U")].copy()
    if bound_mode.startswith("Lower"):
        return df[df["MetricBound"].astype(str).str.upper().eq("L")].copy()
    return df

def build_id_cols(per_channel: bool, per_bead: bool) -> list[str]:
    cols = ["Class", "Sub-class", "Stat"]
    if per_channel:
        cols.append("Channel")
    if per_bead:
        cols.append("Bead")
    return cols

def pivot_wide(df: pd.DataFrame, id_cols: list[str], agg: str) -> tuple[pd.DataFrame, list[str]]:
    """
    Use Metrics as feature columns (SUMP_L, SUMP_U, MAXP_L, MAXP_U).
    We always pivot by Metrics (no user metric selection).
    """
    tmp = df.copy()
    tmp["_feature_"] = tmp["Metrics"].astype(str)

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
    feat_cols = [c for c in wide.columns if c not in id_cols]
    return wide, feat_cols

def fit_pca(wide: pd.DataFrame, id_cols: list[str], feat_cols: list[str], n_components: int, standardize: bool):
    X = wide[feat_cols].astype(float)

    # drop rows with all-NaN features
    keep = ~X.isna().all(axis=1)
    wide2 = wide.loc[keep].copy()
    X = X.loc[keep].copy()

    if X.shape[0] == 0:
        raise ValueError("No rows remain after filtering (all-NaN features).")

    # fill remaining NaNs with column mean
    X = X.apply(lambda s: s.fillna(s.mean()), axis=0)

    # standardize
    X_used = StandardScaler().fit_transform(X.values) if standardize else X.values

    pca = PCA(n_components=n_components, random_state=0)
    Z = pca.fit_transform(X_used)
    var = pca.explained_variance_ratio_

    out = wide2.copy()
    out["PC1"] = Z[:, 0]
    out["PC2"] = Z[:, 1] if n_components >= 2 else 0.0
    out["PC3"] = Z[:, 2] if n_components >= 3 else 0.0
    return out, var

def is_valid_hex(s: str) -> bool:
    s = (s or "").strip()
    if not s.startswith("#"):
        return False
    if len(s) not in (7, 9):  # #RRGGBB or #RRGGBBAA
        return False
    # basic hex chars check
    try:
        int(s[1:], 16)
        return True
    except Exception:
        return False

# =========================
# UI
# =========================
st.title("PCA Explorer (2D/3D) — Plotly (Focused)")
st.caption(
    "Uses all Metrics by default (e.g., SUMP_L/SUMP_U/MAXP_L/MAXP_U). "
    "You choose point identity (per Channel / per Bead / Channel–Bead) and optionally Upper/Lower only."
)

with st.sidebar:
    st.header("1) Upload")
    uploaded = st.file_uploader("Upload CSV (or XLSX)", type=["csv", "xlsx", "xls"])

if not uploaded:
    st.info("Upload a file to begin. Expected columns: " + ", ".join(REQUIRED_COLS))
    st.stop()

# Load early (so sidebar can show unique values for color picker)
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

# ===== Sidebar controls (need df_long loaded) =====
with st.sidebar:
    st.header("2) PCA Dimension")
    dim = st.radio("2D or 3D", ["2D", "3D"], index=1)
    requested_components = 3 if dim == "3D" else 2

    st.header("3) Point identity")
    per_channel = st.checkbox("Per Channel", value=True)
    per_bead = st.checkbox("Per Bead", value=True)
    st.caption("If both checked → points are Channel–Bead pairs. If neither → all together (per Class/Sub-class/Stat).")

    st.header("4) Use Upper/Lower")
    bound_mode = st.selectbox(
        "Metrics bound",
        ["Both (Upper + Lower)", "Upper only (_U)", "Lower only (_L)"],
        index=0,
    )

    st.header("5) Aggregation")
    agg = st.selectbox("Aggregate duplicates (pivot)", ["mean", "median", "min", "max", "sum"], index=0)

    st.header("6) Standardize")
    standardize = st.checkbox("Standardize features (recommended)", value=True)

    st.header("7) Color settings")
    color_by = st.selectbox("Color points by", ["Stat", "Class", "Channel", "Bead"], index=0)

    st.header("8) Figure height")
    fig_height = st.slider("Height (px)", 400, 1400, 750, 50)

# Build a preview dataframe for color categories (respecting current filters)
df_preview = filter_by_bound(df_long, bound_mode)
id_cols_preview = build_id_cols(per_channel=per_channel, per_bead=per_bead)

# If color_by isn't present (e.g., Channel unchecked but user selects Channel), still allow, but will fallback later
color_vals = []
if color_by in df_preview.columns:
    color_vals = sorted(df_preview[color_by].astype(str).unique().tolist())

# Sidebar HEX inputs (BEFORE Start Plotting)
with st.sidebar:
    st.subheader("HEX color map (optional)")
    st.caption("Provide per-category HEX (e.g., #FF0000). Leave blank for Plotly defaults.")

    # Keep inputs stable across reruns
    if "hex_map" not in st.session_state:
        st.session_state["hex_map"] = {}

    # Only show inputs if we have categories
    if color_vals:
        for v in color_vals:
            key = f"hex__{color_by}__{v}"
            default_val = st.session_state["hex_map"].get((color_by, v), "")
            inp = st.text_input(str(v), value=default_val, key=key, placeholder="#RRGGBB")
            st.session_state["hex_map"][(color_by, v)] = inp
    else:
        st.write("(No categories to map yet)")

    st.divider()
    start = st.button("▶ Start Plotting", type="primary", use_container_width=True)

if not start:
    st.warning("Set options in the sidebar, then click **Start Plotting**.")
    st.stop()

# ===== Build final dataset (respecting filters) =====
df_use = filter_by_bound(df_long, bound_mode)
id_cols = build_id_cols(per_channel=per_channel, per_bead=per_bead)

# Pivot (always Metrics as features)
try:
    wide, feat_cols = pivot_wide(df_use, id_cols=id_cols, agg=agg)
except Exception as e:
    st.error(f"Pivot failed: {e}")
    st.stop()

# Decide feasible PCA dimensionality
n_features = len(feat_cols)
if n_features == 0:
    st.error("No feature columns found after pivot. Check your Metrics column / filters.")
    st.stop()

n_components = min(requested_components, n_features)
if requested_components > n_components:
    st.warning(
        f"Requested {requested_components}D PCA but only {n_features} feature(s) available "
        f"(because of your Upper/Lower selection). Using PCA({n_components}) instead."
    )

# Fit PCA (or PCA(1) if only 1 feature remains)
try:
    pca_df, var = fit_pca(wide, id_cols=id_cols, feat_cols=feat_cols, n_components=max(1, n_components), standardize=standardize)
except Exception as e:
    st.error(f"PCA failed: {e}")
    st.stop()

# Determine color column
color_col = color_by if color_by in pca_df.columns else "Stat"
if color_col not in pca_df.columns:
    # last resort: create a single category
    pca_df["__all__"] = "ALL"
    color_col = "__all__"

# Build color map from sidebar inputs
color_map = {}
for (cb, v), hexv in st.session_state.get("hex_map", {}).items():
    if cb == color_by and is_valid_hex(hexv):
        color_map[str(v)] = hexv.strip()

# Hover data
hover_cols = [c for c in ["Class", "Sub-class", "Stat", "Channel", "Bead"] if c in pca_df.columns]

# ===== Plot =====
title = (
    f"PCA ({'3D' if requested_components==3 else '2D'}) | "
    f"point_id={'+'.join(id_cols)} | bound={bound_mode} | agg={agg} | "
    f"standardize={standardize} | features={feat_cols} | explained_var={np.round(var,3)}"
)

left, right = st.columns([2, 1], gap="large")

with left:
    # If user asked 3D but PCA has <3 components, we still plot consistently:
    # - If PCA(2): use 2D scatter
    # - If PCA(1): use 1D embedded into 2D (PC2=0)
    if requested_components == 3 and n_components >= 3:
        fig = px.scatter_3d(
            pca_df,
            x="PC1", y="PC2", z="PC3",
            color=color_col,
            color_discrete_map=color_map if color_map else None,
            hover_data=hover_cols,
            title=title,
        )
        fig.update_traces(marker=dict(size=5))
        fig.update_layout(height=fig_height)
        st.plotly_chart(fig, use_container_width=True)
    else:
        # 2D view (PC2 might be 0 if only 1 feature/component)
        fig = px.scatter(
            pca_df,
            x="PC1", y="PC2",
            color=color_col,
            color_discrete_map=color_map if color_map else None,
            hover_data=hover_cols,
            title=title,
        )
        fig.update_traces(marker=dict(size=8))
        fig.update_layout(height=fig_height)
        st.plotly_chart(fig, use_container_width=True)

with right:
    st.subheader("Summary")
    st.write(f"- Points: **{len(pca_df)}**")
    st.write(f"- Point identity: **{'+'.join(id_cols)}**")
    st.write(f"- Feature count: **{len(feat_cols)}**")
    st.write(f"- Feature names: **{', '.join(map(str, feat_cols))}**")
    st.write(f"- PCA components used: **{n_components}**")
    st.write(f"- Explained variance: **{np.round(var, 4)}**")

    st.subheader("Download")
    csv_bytes = pca_df.to_csv(index=False).encode("utf-8")
    st.download_button(
        "Download PCA table as CSV",
        data=csv_bytes,
        file_name="pca_table.csv",
        mime="text/csv",
        use_container_width=True,
    )

    with st.expander("Preview (first 50 rows)"):
        st.dataframe(pca_df.head(50), use_container_width=True)
