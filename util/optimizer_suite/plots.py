# plots.py  –  Thesis visualisations for the path optimisation suite
# Call plot_results(stats, overall) from your Streamlit app.

from pathlib import Path

import pandas as pd
import plotly.express as px
import plotly.graph_objects as go
import streamlit as st


# ── Internal helpers ───────────────────────────────────────────────────────────


def _flatten(df: pd.DataFrame) -> pd.DataFrame:
    """
    Flatten a MultiIndex column DataFrame produced by .agg([...]).
    ("travel_time_s", "mean")  →  "travel_time_s_mean"
    ("is_deterministic", "")   →  "is_deterministic"
    Also resets the row index so svg_path / optimizer become plain columns.
    """
    df = df.copy()
    df.columns = [
        "_".join(c for c in col if c) if isinstance(col, tuple) else col
        for col in df.columns
    ]
    return df.reset_index()


def _color_map(keys: list[str]) -> dict[str, str]:
    palette = px.colors.qualitative.Set2
    return {k: palette[i % len(palette)] for i, k in enumerate(keys)}


def _stacked_bar_traces(
    x_vals: list,
    net_benefit: list[float],
    time_reduction: list[float],
    std_time_reduction: list[float],
    label: str,
    color: str,
    offset_index: int,
    is_deterministic: bool,
    show_in_legend: bool,
) -> tuple[go.Bar, go.Bar]:
    """
    Return two Bar traces that together form one stacked group entry:
      - bottom (solid):   net_benefit_s
      - top (hatched):    time_reduction_s - net_benefit_s  (the optimizer's own runtime cost)
    Total bar height = time_reduction_s.
    Error bar (std of time_reduction) shown only for stochastic optimizers.
    """
    runtime_cost = [max(tr - nb, 0.0) for tr, nb in zip(time_reduction, net_benefit)]

    bottom = go.Bar(
        x=x_vals,
        y=net_benefit,
        name=label,
        offsetgroup=offset_index,
        legendgroup=label,
        showlegend=show_in_legend,
        marker_color=color,
        hovertemplate="<b>%{x}</b><br>Net benefit: %{y:.2f} s<extra>"
        + label
        + "</extra>",
    )

    top = go.Bar(
        x=x_vals,
        y=runtime_cost,
        base=net_benefit,
        name=f"{label} (optimizer cost)",
        offsetgroup=offset_index,
        legendgroup=label,
        showlegend=False,
        marker_color=color,
        marker_opacity=0.4,
        marker_pattern_shape="/",
        error_y=(
            dict(type="data", array=std_time_reduction, visible=True)
            if not is_deterministic
            else None
        ),
        hovertemplate=(
            "<b>%{x}</b><br>Optimizer runtime cost: %{y:.2f} s<extra>"
            + label
            + "</extra>"
        ),
    )

    return bottom, top


# ── Public API ─────────────────────────────────────────────────────────────────


def plot_results(stats: pd.DataFrame, overall: pd.DataFrame) -> None:
    """
    Render all four thesis plots in Streamlit.

    Parameters
    ----------
    stats:
        Result of groupby(["svg_path", "optimizer"]).agg(["mean","std","min","max","median"]),
        with flat columns `is_deterministic` (bool) and `problem_size` (int) added afterwards.
    overall:
        Result of groupby("optimizer").agg(["mean","std","min","max","median"]),
        with flat columns `is_deterministic` and `problem_size` added afterwards.

    Both DataFrames are expected to cover these metric columns:
        travel_time_s, wall_clock_time_s, process_time_s,
        time_reduction_s, net_benefit_pct, net_benefit_s
    """

    flat = _flatten(stats).fillna(0)
    flat_ov = _flatten(overall).fillna(0)

    flat["problem"] = flat["svg_path"].apply(lambda p: Path(p).stem)

    optimizers_and_original: list[str] = list(flat["optimizer"].unique())
    optimizers: list[str] = optimizers_and_original.copy()
    optimizers.remove("Original")
    problems: list[str] = list(flat["problem"].unique())

    opt_colors = _color_map(optimizers_and_original)
    prob_colors = _color_map(problems)

    # ── Chart 1: Stacked bars — grouped by problem ─────────────────────────
    st.subheader("Time Reduction & Net Benefit — grouped by problem")
    st.caption(
        "**Solid fill** = net benefit (time saved on the cut minus the optimizer's own runtime).  "
        "**Hatched fill** = time the optimizer itself consumed.  "
        "**Total bar height** = raw time reduction vs. the unoptimised order.  "
        "Error bars show std across runs (stochastic optimizers only)."
    )

    fig1 = go.Figure()
    for i, optimizer in enumerate(optimizers):
        subset = (
            flat[flat["optimizer"] == optimizer].set_index("problem").reindex(problems)
        )
        is_det = bool(subset["is_deterministic"].iloc[0])
        bottom, top = _stacked_bar_traces(
            x_vals=problems,
            net_benefit=subset["net_benefit_s_mean"].fillna(0).tolist(),
            time_reduction=subset["time_reduction_s_mean"].fillna(0).tolist(),
            std_time_reduction=subset["time_reduction_s_std"].fillna(0).tolist(),
            label=optimizer,
            color=opt_colors[optimizer],
            offset_index=i,
            is_deterministic=is_det,
            show_in_legend=True,
        )
        fig1.add_traces([bottom, top])

    fig1.update_layout(
        barmode="group",
        xaxis_title="Problem",
        yaxis_title="Time (s)",
        legend_title="Optimizer",
        height=520,
        xaxis_tickangle=-35,
    )
    st.plotly_chart(fig1, use_container_width=True)

    st.divider()

    # ── Chart 2: Stacked bars — grouped by optimizer ───────────────────────
    st.subheader("Time Reduction & Net Benefit — grouped by optimizer")
    st.caption(
        "Same data as above; grouping flipped to show how consistently "
        "each optimizer performs across all problems."
    )

    fig2 = go.Figure()
    for j, problem in enumerate(problems):
        subset = (
            flat[flat["problem"] == problem].set_index("optimizer").reindex(optimizers)
        )
        is_det_per_opt = subset["is_deterministic"].tolist()
        std_tr = subset["time_reduction_s_std"].fillna(0).tolist()
        net_benefit = subset["net_benefit_s_mean"].fillna(0).tolist()
        time_reduction = subset["time_reduction_s_mean"].fillna(0).tolist()
        runtime_cost = [
            max(tr - nb, 0.0) for tr, nb in zip(time_reduction, net_benefit)
        ]
        color = prob_colors[problem]

        fig2.add_trace(
            go.Bar(
                x=optimizers,
                y=net_benefit,
                name=problem,
                offsetgroup=j,
                legendgroup=problem,
                showlegend=True,
                marker_color=color,
                hovertemplate=(
                    "<b>%{x}</b><br>Net benefit: %{y:.2f} s<extra>"
                    + problem
                    + "</extra>"
                ),
            )
        )
        fig2.add_trace(
            go.Bar(
                x=optimizers,
                y=runtime_cost,
                base=net_benefit,
                name=f"{problem} (optimizer cost)",
                offsetgroup=j,
                legendgroup=problem,
                showlegend=False,
                marker_color=color,
                marker_opacity=0.4,
                marker_pattern_shape="/",
                # Zero out std for deterministic optimizers so their error bars disappear
                error_y=dict(
                    type="data",
                    array=[s if not d else 0.0 for s, d in zip(std_tr, is_det_per_opt)],
                    visible=True,
                ),
                hovertemplate=(
                    "<b>%{x}</b><br>Optimizer runtime cost: %{y:.2f} s<extra>"
                    + problem
                    + "</extra>"
                ),
            )
        )

    fig2.update_layout(
        barmode="group",
        xaxis_title="Optimizer",
        yaxis_title="Time (s)",
        legend_title="Problem",
        height=520,
    )
    st.plotly_chart(fig2, use_container_width=True)

    st.divider()

    # ── Chart 3: Pareto scatter ────────────────────────────────────────────
    st.subheader("Pareto: Optimizer Runtime vs. Time Reduction")
    st.caption(
        "Each point is one optimizer, aggregated across all problems.  "
        "**Points above the dashed line** have positive net benefit — "
        "they save more machine time than they consume.  "
        "Error bars show std across runs (stochastic optimizers only)."
    )

    fig3 = go.Figure()
    for optimizer in flat_ov["optimizer"].tolist():
        row = flat_ov[flat_ov["optimizer"] == optimizer].iloc[0]
        is_det = bool(row["is_deterministic"])

        fig3.add_trace(
            go.Scatter(
                x=[row["wall_clock_time_s_mean"]],
                y=[row["time_reduction_s_mean"]],
                mode="markers+text",
                name=optimizer,
                marker=dict(size=14, color=opt_colors.get(optimizer, "grey")),
                text=[optimizer],
                textposition="top center",
                error_x=(
                    dict(
                        type="data", array=[row["wall_clock_time_s_std"]], visible=True
                    )
                    if not is_det
                    else None
                ),
                error_y=(
                    dict(type="data", array=[row["time_reduction_s_std"]], visible=True)
                    if not is_det
                    else None
                ),
                hovertemplate=(
                    f"<b>{optimizer}</b><br>"
                    "Mean runtime: %{x:.3f} s<br>"
                    "Mean time reduction: %{y:.2f} s"
                    "<extra></extra>"
                ),
            )
        )

    # Break-even diagonal: y = x means net benefit = 0
    max_val = (
        max(
            flat_ov["wall_clock_time_s_mean"].max(),
            flat_ov["time_reduction_s_mean"].max(),
        )
        * 1.15
    )
    fig3.add_trace(
        go.Scatter(
            x=[0, max_val],
            y=[0, max_val],
            mode="lines",
            line=dict(dash="dash", color="lightgrey", width=1.5),
            name="Break-even (net benefit = 0)",
            hoverinfo="skip",
        )
    )

    fig3.update_layout(
        xaxis_title="Mean optimizer runtime (s)",
        yaxis_title="Mean time reduction (s)",
        legend_title="Optimizer",
        height=520,
    )
    st.plotly_chart(fig3, use_container_width=True)

    st.divider()

    # ── Chart 4: Runtime vs. problem size ─────────────────────────────────
    st.subheader("Optimizer Runtime vs. Problem Size")
    st.caption(
        "Shows how each optimizer's runtime scales with problem complexity. "
        "Error bands show std across runs (stochastic optimizers only)."
    )

    fig4 = go.Figure()
    for optimizer in optimizers:
        subset = flat[flat["optimizer"] == optimizer].sort_values("problem_size")
        is_det = bool(subset["is_deterministic"].iloc[0])

        fig4.add_trace(
            go.Scatter(
                x=subset["problem_size"].tolist(),
                y=subset["wall_clock_time_s_mean"].tolist(),
                mode="lines+markers",
                name=optimizer,
                marker=dict(color=opt_colors[optimizer], size=8),
                line=dict(color=opt_colors[optimizer]),
                error_y=(
                    dict(
                        type="data",
                        array=subset["wall_clock_time_s_std"].tolist(),
                        visible=True,
                    )
                    if not is_det
                    else None
                ),
                hovertemplate=(
                    "Problem size: %{x}<br>"
                    "Mean runtime: %{y:.3f} s"
                    f"<extra>{optimizer}</extra>"
                ),
            )
        )

    fig4.update_layout(
        xaxis_title="Problem size (number of cuts)",
        yaxis_title="Mean wall clock time (s)",
        legend_title="Optimizer",
        height=520,
    )
    st.plotly_chart(fig4, use_container_width=True)
