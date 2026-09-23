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
    runtime_cost = [
        -(tr - nb) if nb < 0 else (tr - nb)
        for tr, nb in zip(time_reduction, net_benefit)
    ]

    net_benefit_bar = go.Bar(
        x=x_vals,
        y=net_benefit,
        name=label,
        offsetgroup=offset_index,
        legendgroup=label,
        showlegend=show_in_legend,
        marker_color=color,
        error_y=(
            dict(type="data", array=std_time_reduction, visible=not is_deterministic)
        ),
        hovertemplate="<b>%{x}</b><br>Net benefit: %{y:.2f} s<extra>"
        + label
        + "</extra>",
    )

    runtime_bar = go.Bar(
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
        error_y=(dict(type="data", array=std_time_reduction, visible=True)),
        hovertemplate=(
            "<b>%{x}</b><br>Optimizer runtime cost: %{y:.2f} s<extra>"
            + label
            + "</extra>"
        ),
    )

    return net_benefit_bar, runtime_bar


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

    flat["problem"] = flat["svg_path"].apply(lambda p: Path(p).stem)

    optimizers_and_original: list[str] = list(flat["optimizer"].unique())
    optimizers: list[str] = optimizers_and_original.copy()
    optimizers.remove("Original")
    problems: list[str] = list(flat["problem"].unique())

    opt_colors = _color_map(optimizers_and_original)

    # ── Chart 1: Stacked bars — grouped by problem ─────────────────────────
    st.subheader("Wall-clock runtime — grouped by problem")
    st.caption(
        "**Bar height** = Wall-clock time in secondsError bars show std across runs"
    )

    fig1 = go.Figure()
    fig2 = go.Figure()
    fig3 = go.Figure()
    fig4 = go.Figure()
    for i, optimizer in enumerate(optimizers):
        subset = (
            flat[flat["optimizer"] == optimizer].set_index("problem").reindex(problems)
        )
        wallclock_bar = go.Bar(
            x=problems,
            y=subset["wall_clock_time_s_mean"].fillna(0).tolist(),
            name=optimizer,
            offsetgroup=i,
            legendgroup=optimizer,
            showlegend=True,
            marker_color=opt_colors[optimizer],
            error_y=(
                dict(
                    type="data",
                    array=subset["wall_clock_time_s_std"].fillna(0).tolist(),
                    visible=True,
                )
            ),
            hovertemplate=(
                "<b>%{x}</b><br>Optimizer runtime: %{y:.2f} s<extra>"
                + optimizer
                + "</extra>"
            ),
        )
        fig1.add_trace(wallclock_bar)

        traveltime_bar = go.Bar(
            x=problems,
            y=subset["travel_time_s_mean"].fillna(0).tolist(),
            name=optimizer,
            showlegend=True,
            marker_color=opt_colors[optimizer],
            error_y=(
                dict(
                    type="data",
                    array=subset["travel_time_s_std"].fillna(0).tolist(),
                    visible=True,
                )
            ),
            hovertemplate=(
                "<b>%{x}</b><br>Total travel time: %{y:.2f} s<extra>"
                + optimizer
                + "</extra>"
            ),
        )
        fig2.add_trace(traveltime_bar)

        is_det = bool(subset["is_deterministic"].iloc[0])
        net_benefit_bar, runtime_bar = _stacked_bar_traces(
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
        fig3.add_traces([net_benefit_bar, runtime_bar])

        subset = flat[flat["optimizer"] == optimizer].sort_values("problem_size")

        fig4.add_trace(
            go.Scatter(
                x=subset["problem_size"].tolist(),
                y=subset["wall_clock_time_s_mean"].tolist(),
                customdata=subset["problem"].tolist(),
                mode="lines+markers",
                name=optimizer,
                marker=dict(color=opt_colors[optimizer], size=8),
                line=dict(color=opt_colors[optimizer]),
                hovertemplate=(
                    "Problem: %{customdata}<br>"
                    "Problem size: %{x}<br>"
                    "Mean runtime: %{y:.3f} s"
                    f"<extra>{optimizer}</extra>"
                ),
            )
        )

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

    st.subheader("Total travel time — grouped by problem")
    st.caption(
        "**Bar height** = Total travel time time in seconds"
        "Error bars show std across runs"
    )

    fig2.update_layout(
        barmode="group",
        xaxis_title="Optimizer",
        yaxis_title="Travel Time (s)",
        legend_title="Problem",
        height=520,
    )
    st.plotly_chart(fig2, use_container_width=True)

    st.divider()

    st.subheader("Time Reduction & Net Benefit — grouped by problem")
    st.caption(
        "**Solid fill** = net benefit (time saved on the cut minus the optimizer's own runtime).  "
        "**Hatched fill** = time the optimizer itself consumed.  "
        "**Total bar height** = raw time reduction vs. the unoptimised order.  "
        "Error bars show std across runs (stochastic optimizers only)."
    )

    st.plotly_chart(fig3, use_container_width=True)

    st.divider()

    # ── Chart 4: Runtime vs. problem size ─────────────────────────────────
    st.subheader("Optimizer Runtime vs. Problem Size")
    st.caption(
        "Shows how each optimizer's net benefit scales with problem complexity. "
        "Error bands show std across runs (stochastic optimizers only)."
    )

    fig4.update_layout(
        xaxis_title="Problem size (number of cuts)",
        yaxis_title="Net benefit (s)",
        legend_title="Optimizer",
        height=520,
    )
    st.plotly_chart(fig4, use_container_width=True)
