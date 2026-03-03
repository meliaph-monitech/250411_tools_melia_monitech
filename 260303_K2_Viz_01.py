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
    Adds MetricFamily (SUMP/MAXP) and MetricBound (L/U).
    """
    out = df.copy()
    parts = out["Metrics"].astype(str).str.split("_", n=1, expand=True)
    out["MetricFamily"] = parts[0]
    out["MetricBound"] = parts[1] if parts.shape[1] > 1 else ""
    out["MetricBound"] = out["MetricBound"].astype(str).str.upper()
    return out


def pivot_wide(df: pd.DataFrame, id_cols: list[str], agg: str) -> tuple[pd.DataFrame, list[str]]:
    """
    Always pivot by Metrics => columns like SUMP_L, SUMP_U, MAXP_L, MAXP_U (or subset if filtered).
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
    """
    - Drops rows where ALL features are NaN
    - Fills remaining NaNs by column mean
    - PCA on standardized (optional) data
    """
    X = wide[feat_cols].astype(float)

    keep = ~X.isna().all(axis=1)
    wide2 = wide.loc[keep].copy()
    X = X.loc[keep].copy()

    if X.shape[0] == 0:
        raise ValueError("No rows remain after filtering (all-NaN features).")

    # Fill remaining NaNs
    X = X.apply(lambda s: s.fillna(s.mean()), axis=0)

    if standardize:
        X_used = StandardScaler().fit_transform(X.values)
    else:
        X_used = X.values

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
    try:
        int(s[1:], 16)
        return True
    except Exception:
        return False


def safe_str(x) -> str:
    return "" if pd.isna(x) else str(x)


def make_group_keys(df: pd.DataFrame, group_cols: list[str]) -> list[tuple]:
    if not group_cols:
        return [tuple()]
    keys = (
        df[group_cols]
        .drop_duplicates()
        .sort_values(group_cols)
        .apply(lambda r: tuple(r.values.tolist()), axis=1)
        .tolist()
    )
    return keys


def filter_by_group(df: pd.DataFrame, group_cols: list[str], key: tuple) -> pd.DataFrame:
    if not group_cols:
        return df
    out = df
    for col, val in zip(group_cols, key):
        out = out[out[col].astype(str) == str(val)]
    return out


# =========================
# App
# =========================
st.title("PCA Explorer (2D/3D) — Plotly (Multi-figure by Group)")
st.caption(
    "Uses all metrics by default (SUMP_L/SUMP_U/MAXP_L/MAXP_U). "
    "You can generate multiple figures by Channel, Bead, and Upper/Lower (U/L) in the same way."
)

with st.sidebar:
    st.header("1) Upload")
    uploaded = st.file_uploader("Upload CSV (or XLSX)", type=["csv", "xlsx", "xls"])

if not uploaded:
    st.info("Upload a file to begin. Expected columns: " + ", ".join(REQUIRED_COLS))
    st.stop()

# Load + validate early (so we can show color mapping inputs before Start Plotting)
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

# -------------------------
# Sidebar Controls
# -------------------------
with st.sidebar:
    st.header("2) PCA Dimension")
    dim = st.radio("2D or 3D", ["2D", "3D"], index=1)
    requested_components = 3 if dim == "3D" else 2

    st.header("3) Grouping (generate separate figures)")
    st.caption("These are treated the same way: each selected dimension multiplies the number of figures.")
    per_channel_fig = st.checkbox("Per Channel (separate figures)", value=False)
    per_bead_fig = st.checkbox("Per Bead (separate figures)", value=True)
    per_bound_fig = st.checkbox("Per Upper/Lower (separate figures)", value=False)

    st.header("4) Aggregation / Preprocess")
    agg = st.selectbox("Aggregate duplicates (pivot)", ["mean", "median", "min", "max", "sum"], index=0)
    standardize = st.checkbox("Standardize features (recommended)", value=True)

    st.header("5) Coloring")
    color_by = st.selectbox("Color points by", ["Stat", "Class", "Channel", "Bead", "MetricBound"], index=0)

    st.header("6) Figure height")
    fig_height = st.slider("Height (px)", 400, 1600, 800, 50)

# Build group columns list (for multi-figure)
group_cols = []
if per_channel_fig:
    group_cols.append("Channel")
if per_bead_fig:
    group_cols.append("Bead")
if per_bound_fig:
    group_cols.append("MetricBound")

# Color category list (global, so user can set HEX before plotting)
if color_by not in df_long.columns:
    color_categories = []
else:
    color_categories = sorted(df_long[color_by].astype(str).unique().tolist())

with st.sidebar:
    st.subheader("HEX color map (optional)")
    st.caption("Provide HEX per category (e.g., #FF0000). Leave blank to use Plotly defaults.")

    if "hex_map_global" not in st.session_state:
        st.session_state["hex_map_global"] = {}

    if color_categories:
        for v in color_categories:
            key = f"hex__{color_by}__{v}"
            default_val = st.session_state["hex_map_global"].get((color_by, v), "")
            inp = st.text_input(str(v), value=default_val, key=key, placeholder="#RRGGBB")
            st.session_state["hex_map_global"][(color_by, v)] = inp
    else:
        st.write("(No categories available)")

    st.divider()
    start = st.button("▶ Start Plotting", type="primary", use_container_width=True)

if not start:
    st.warning("Set options in the sidebar, then click **Start Plotting**.")
    st.stop()

# Build color map dict
color_map = {}
for (cb, v), hexv in st.session_state.get("hex_map_global", {}).items():
    if cb == color_by and is_valid_hex(hexv):
        color_map[str(v)] = hexv.strip()

# -------------------------
# Plotting logic (Design B): separate PCA per group figure
# -------------------------
base_id_cols = ["Class", "Sub-class", "Stat"]  # inside each figure, points are defined by this base identity

keys = make_group_keys(df_long, group_cols)

st.subheader("Plots")

# Quick summary of how many figures
if group_cols:
    st.caption(f"Generating **{len(keys)}** figure(s) by: **{', '.join(group_cols)}**")
else:
    st.caption("Generating **1** figure (no grouping).")

# Render figures
for idx, key in enumerate(keys, start=1):
    df_g = filter_by_group(df_long, group_cols, key)

    # If grouping by MetricBound, within a group only U or only L => fewer metric columns will exist.
    # We still pivot by Metrics. PCA dimensionality will adapt automatically.

    # Pivot
    try:
        wide, feat_cols = pivot_wide(df_g, id_cols=base_id_cols, agg=agg)
    except Exception as e:
        st.error(f"[Group {idx}] Pivot failed: {e}")
        continue

    # if len(feat_cols) == 0:
    #     st.warning(f"[Group {idx}] No feature columns after pivot. Skipping.")
    #     continue

    # # Decide feasible PCA components
    # n_features = len(feat_cols)
    # n_components = min(requested_components, n_features)

    # -------------------------------------------------
    # FORCE ALL 4 METRICS TO EXIST (prevents zero rows from disappearing)
    # -------------------------------------------------
    EXPECTED_METRICS = ["SUMP_L", "SUMP_U", "MAXP_L", "MAXP_U"]
    
    for m in EXPECTED_METRICS:
        if m not in wide.columns:
            wide[m] = 0.0  # create missing metric column as 0
    
    # Use consistent feature order
    feat_cols = EXPECTED_METRICS
    
    # Fill any remaining NaN with 0
    wide[feat_cols] = wide[feat_cols].astype(float).fillna(0.0)
    
    # Now PCA dimension logic
    n_features = len(feat_cols)
    n_components = min(requested_components, n_features)

    # Run PCA
    try:
        pca_df, var = fit_pca(
            wide=wide,
            id_cols=base_id_cols,
            feat_cols=feat_cols,
            n_components=max(1, n_components),
            standardize=standardize,
        )
    except Exception as e:
        st.error(f"[Group {idx}] PCA failed: {e}")
        continue

    # Choose color column (must exist in this pca_df; it will, because base_id_cols include Stat/Class, but not always Channel/Bead/Bound)
    # If user chooses to color by a grouped dimension, it is constant within the figure and still exists only if we add it.
    # So we attach group values as columns for hover/color convenience.
    for col, val in zip(group_cols, key):
        pca_df[col] = str(val)

    color_col = color_by if color_by in pca_df.columns else "Stat"
    if color_col not in pca_df.columns:
        pca_df["__all__"] = "ALL"
        color_col = "__all__"

    # Hover
    hover_cols = [c for c in ["Class", "Sub-class", "Stat", "Channel", "Bead", "MetricBound"] if c in pca_df.columns]

    # Title per figure
    if group_cols:
        group_label = ", ".join([f"{c}={safe_str(v)}" for c, v in zip(group_cols, key)])
    else:
        group_label = "ALL"

    # If requested 3D but only 2 features (e.g., Upper-only), we show 2D plot for that figure.
    show_3d = (requested_components == 3 and n_components >= 3)

    title = (
        f"[{idx}/{len(keys)}] {group_label} | "
        f"PCA_dim={'3D' if show_3d else '2D'} | features={feat_cols} | "
        f"agg={agg} | standardize={standardize} | explained_var={np.round(var, 3)}"
    )

    with st.expander(title, expanded=(idx == 1)):
        # Plot
        if show_3d:
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

        # Summary + download for this group
        c1, c2 = st.columns([1, 1])
        with c1:
            st.write(f"- Points: **{len(pca_df)}**")
            st.write(f"- Features: **{len(feat_cols)}**")
            st.write(f"- PCA components used: **{n_components}**")
            st.write(f"- Explained variance: **{np.round(var, 4)}**")
        with c2:
            csv_bytes = pca_df.to_csv(index=False).encode("utf-8")
            st.download_button(
                f"Download this group CSV ({idx})",
                data=csv_bytes,
                file_name=f"pca_group_{idx}.csv",
                mime="text/csv",
                use_container_width=True,
            )

        st.dataframe(pca_df.head(50), use_container_width=True)
