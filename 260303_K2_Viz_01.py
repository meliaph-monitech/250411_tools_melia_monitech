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
    out = df.copy()
    parts = out["Metrics"].astype(str).str.split("_", n=1, expand=True)
    out["MetricFamily"] = parts[0]
    out["MetricBound"] = parts[1] if parts.shape[1] > 1 else ""
    return out

def pick_id_cols(include_channel: bool, include_bead: bool, include_metricfamily: bool) -> list[str]:
    cols = ["Class", "Sub-class", "Stat"]
    if include_channel:
        cols.append("Channel")
    if include_bead:
        cols.append("Bead")
    if include_metricfamily:
        cols.append("MetricFamily")
    return cols

def filter_metrics(df: pd.DataFrame, metrics_selected: list[str]) -> pd.DataFrame:
    if not metrics_selected:
        return df
    return df[df["Metrics"].isin(metrics_selected)].copy()

def pivot_wide(df: pd.DataFrame, id_cols: list[str], feature_mode: str, agg: str) -> tuple[pd.DataFrame, list[str]]:
    tmp = df.copy()

    if feature_mode == "Per Metrics (SUMP_L, SUMP_U, MAXP_L, MAXP_U)":
        tmp["_feature_"] = tmp["Metrics"].astype(str)
    elif feature_mode == "Per Metrics Group only (SUMP vs MAXP) [collapse L/U]":
        tmp["_feature_"] = tmp["MetricFamily"].astype(str)
    else:
        # Group + Bound (SUMP__L, ...)
        tmp["_feature_"] = tmp[["MetricFamily", "MetricBound"]].astype(str).agg("__".join, axis=1)

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

def fit_pca(wide: pd.DataFrame, id_cols: list[str], feature_cols: list[str], n_components: int, standardize: bool):
    X = wide[feature_cols].astype(float)

    keep = ~X.isna().all(axis=1)
    wide2 = wide.loc[keep].copy()
    X = X.loc[keep].copy()

    if X.shape[0] == 0:
        raise ValueError("No rows remain after filtering (all-NaN features).")
    X = X.apply(lambda s: s.fillna(s.mean()), axis=0)

    if X.shape[1] < n_components:
        raise ValueError(f"Not enough features ({X.shape[1]}) for PCA({n_components}).")

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

def aggregate_rowwise(X: pd.DataFrame, agg: str) -> pd.Series:
    # Row-wise aggregation for "use only aggregate value among chosen metrics"
    if agg == "mean":
        return X.mean(axis=1)
    if agg == "median":
        return X.median(axis=1)
    if agg == "min":
        return X.min(axis=1)
    if agg == "max":
        return X.max(axis=1)
    if agg == "sum":
        return X.sum(axis=1)
    raise ValueError("Unsupported row-wise aggregation")

def build_color_map_ui(unique_vals: list[str], default_palette=None):
    st.write("Assign HEX colors per category (optional). Leave blank to use Plotly defaults.")
    cmap = {}
    for v in unique_vals:
        key = f"color__{v}"
        default = "" if default_palette is None else default_palette.get(v, "")
        cmap[v] = st.text_input(f"{v}", value=default, key=key, placeholder="#RRGGBB")
    # keep only valid-ish hex entries
    cleaned = {k: v.strip() for k, v in cmap.items() if isinstance(v, str) and v.strip().startswith("#") and len(v.strip()) in (7, 9)}
    return cleaned

# =========================
# UI
# =========================
st.title("PCA Explorer (2D/3D) — Plotly (Enhanced)")
st.caption("Interactive PCA exploration with flexible grouping, feature selection, row-wise aggregation option, custom colors, and adjustable figure height.")

with st.sidebar:
    st.header("1) Upload")
    uploaded = st.file_uploader("Upload CSV (or XLSX)", type=["csv", "xlsx", "xls"])

    st.header("2) Plot dimension")
    dim = st.radio("2D or 3D", ["2D", "3D"], index=1)
    n_components = 3 if dim == "3D" else 2

    st.header("3) Grouping (what defines a point?)")
    # (1) Channel
    channel_mode = st.radio("Channel handling", ["Ignore Channel (plot all together)", "Per Channel"], index=1)
    include_channel = channel_mode.startswith("Per")

    # (2) Bead
    bead_mode = st.radio("Bead handling", ["Ignore Bead (plot all together)", "Per Bead"], index=1)
    include_bead = bead_mode.startswith("Per")

    # (3) Metrics Group (SUMP/MAXP) as point split
    metricgroup_as_point = st.radio(
        "Metrics Group handling (as point split)",
        ["Ignore Metrics Group (plot all together)", "Per Metrics Group (SUMP/MAXP)"],
        index=0,
    )
    include_metricfamily_in_id = metricgroup_as_point.startswith("Per")

    st.header("4) Feature definition (columns used for PCA)")
    feature_mode = st.selectbox(
        "Feature columns",
        [
            "Per Metrics (SUMP_L, SUMP_U, MAXP_L, MAXP_U)",
            "Per Metrics Group only (SUMP vs MAXP) [collapse L/U]",
            "Per Group + Bound (SUMP__L, SUMP__U, MAXP__L, MAXP__U)",
        ],
        index=0,
    )

    st.header("5) Choose metrics (optional filter)")
    st.caption("If you select metrics, only those metrics are used before pivot / aggregation.")
    # metrics list shown after file loaded; placeholder for now
    metrics_selected = None

    st.header("6) Value reduction option")
    use_mode = st.radio(
        "Use features for PCA",
        [
            "Use all selected features (multivariate PCA)",
            "Use only ONE aggregate value across selected features (1D -> PCA not needed)",
        ],
        index=0,
    )

    st.header("7) Aggregation")
    agg = st.selectbox("Aggregate duplicates (pivot)", ["mean", "median", "min", "max", "sum"], index=0)

    st.header("8) Standardize")
    standardize = st.checkbox("Standardize features", value=True)

    st.header("9) Figure height")
    fig_height = st.slider("Height (px)", min_value=400, max_value=1400, value=750, step=50)

    st.header("10) Coloring")
    color_by = st.selectbox("Color points by", ["Stat", "Class", "Channel", "Bead", "MetricFamily"], index=0)

    st.divider()
    start = st.button("▶ Start Plotting", type="primary", use_container_width=True)

if not uploaded:
    st.info("Upload a file to begin. Expected columns: " + ", ".join(REQUIRED_COLS))
    st.stop()

# Load + validate
df_long = read_long_table(uploaded)
missing = [c for c in REQUIRED_COLS if c not in df_long.columns]
if missing:
    st.error(f"Missing required columns: {missing}")
    st.stop()

df_long = add_metric_parts(df_long)

# Now that data is loaded, show metrics selection (sidebar needs rerender)
with st.sidebar:
    all_metrics = sorted(df_long["Metrics"].astype(str).unique().tolist())
    metrics_selected = st.multiselect(
        "Select Metrics to include (empty = all)",
        options=all_metrics,
        default=[],
    )

# Only run when user clicks
if not start:
    st.warning("Set options in the sidebar, then click **Start Plotting**.")
    st.stop()

# Apply metric filtering
df_use = filter_metrics(df_long, metrics_selected)

# Build point identity columns
id_cols = pick_id_cols(include_channel, include_bead, include_metricfamily_in_id)

# Pivot wide
try:
    wide, feat_cols = pivot_wide(df_use, id_cols=id_cols, feature_mode=feature_mode, agg=agg)
except Exception as e:
    st.error(f"Pivot failed: {e}")
    st.stop()

# If user selects "single aggregate value", collapse features row-wise into 1 numeric column.
# Then 2D/3D plot is done directly on (value) with a synthetic axis (or jitter) — PCA is not meaningful in 1D.
# But we can still provide a consistent scatter embedding:
#   - 2D: x = agg_value, y = 0
#   - 3D: x = agg_value, y = 0, z = 0
use_single_value = use_mode.startswith("Use only ONE")

if use_single_value:
    if len(feat_cols) == 0:
        st.error("No feature columns to aggregate. Check feature mode / metric selection.")
        st.stop()

    X = wide[feat_cols].astype(float).apply(lambda s: s.fillna(s.mean()), axis=0)
    wide2 = wide.copy()
    wide2["AggValue"] = aggregate_rowwise(X, agg=agg)

    # Standardize single value if requested
    if standardize:
        v = wide2["AggValue"].values.reshape(-1, 1)
        wide2["AggValue"] = StandardScaler().fit_transform(v).ravel()

    plot_df = wide2.copy()
    plot_df["PC1"] = plot_df["AggValue"]
    plot_df["PC2"] = 0.0
    plot_df["PC3"] = 0.0
    var = np.array([1.0, 0.0, 0.0]) if dim == "3D" else np.array([1.0, 0.0])

    # For clarity, rename title wording
    mode_label = "Single aggregate value (no PCA)"
else:
    # PCA
    try:
        plot_df, var = fit_pca(
            wide=wide,
            id_cols=id_cols,
            feature_cols=feat_cols,
            n_components=n_components,
            standardize=standardize,
        )
    except Exception as e:
        st.error(f"PCA failed: {e}")
        st.stop()
    mode_label = "Multivariate PCA"

# Decide hover
hover_cols = [c for c in ["Class", "Sub-class", "Stat", "Channel", "Bead", "MetricFamily"] if c in plot_df.columns]

# Build color map UI based on selected color_by
if color_by not in plot_df.columns:
    color_by_effective = "Stat"
else:
    color_by_effective = color_by

unique_color_vals = sorted(plot_df[color_by_effective].astype(str).unique().tolist())

# Color map inputs (in main area for visibility)
st.subheader("Color customization (optional)")
st.caption(f"Coloring by **{color_by_effective}**. Provide HEX per category (e.g., #FF0000). Leave blank to use defaults.")
color_map = {}
cols = st.columns(3)
for i, v in enumerate(unique_color_vals):
    with cols[i % 3]:
        color_map[v] = st.text_input(f"{v}", value="", placeholder="#RRGGBB", key=f"hex_{color_by_effective}_{v}")
color_map = {k: v.strip() for k, v in color_map.items() if v.strip().startswith("#") and len(v.strip()) in (7, 9)}

# Layout
left, right = st.columns([2, 1], gap="large")

title = (
    f"{dim} | {mode_label} | point_id={'+'.join(id_cols)} | feature_mode={feature_mode} | "
    f"pivot_agg={agg} | standardize={standardize} | explained_var={np.round(var, 3)}"
)

with left:
    if dim == "3D":
        fig = px.scatter_3d(
            plot_df,
            x="PC1", y="PC2", z="PC3",
            color=color_by_effective,
            color_discrete_map=color_map if color_map else None,
            hover_data=hover_cols,
            title=title,
        )
        fig.update_traces(marker=dict(size=5))
        fig.update_layout(height=fig_height)
        st.plotly_chart(fig, use_container_width=True)
    else:
        fig = px.scatter(
            plot_df,
            x="PC1", y="PC2",
            color=color_by_effective,
            color_discrete_map=color_map if color_map else None,
            hover_data=hover_cols,
            title=title,
        )
        fig.update_traces(marker=dict(size=8))
        fig.update_layout(height=fig_height)
        st.plotly_chart(fig, use_container_width=True)

with right:
    st.subheader("Summary")
    st.write(f"- Points: **{len(plot_df)}**")
    st.write(f"- Point identity: **{'+'.join(id_cols)}**")
    st.write(f"- Feature columns (before reduction): **{len(feat_cols)}**")
    st.write(f"- Mode: **{mode_label}**")
    st.write(f"- Explained variance: **{np.round(var, 4)}**")
    st.write("Feature columns:")
    st.code(", ".join(map(str, feat_cols)) if feat_cols else "(none)")

    st.subheader("Download")
    csv_bytes = plot_df.to_csv(index=False).encode("utf-8")
    st.download_button(
        "Download table as CSV",
        data=csv_bytes,
        file_name="pca_table.csv",
        mime="text/csv",
        use_container_width=True,
    )

    with st.expander("Preview data (first 50 rows)"):
        st.dataframe(plot_df.head(50), use_container_width=True)
