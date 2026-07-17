# app.py  –  Path Optimization Suite GUI
# Run with:  streamlit run app.py

import inspect
import os
import tempfile
import types
import typing
from pathlib import Path
from typing import (
    Any,
    Optional,
    Tuple,
    TypeVar,
    TypedDict,
    Union,
    cast,
    get_args,
    get_origin,
    get_type_hints,
)

import pandas as pd
import streamlit as st

from runner import ProblemSettings, run_suite
from core.modules.base_optimizer import BaseOptimizer

# ── Import your optimizer modules here so their subclasses are discovered ──────
# Without these imports, BaseOptimizer.__subclasses__() returns nothing.
# Example:
from core.modules.greedy_optimizer.greedy_optimizer import GreedyOptimizerModule  # noqa: F401
from core.modules.genetic_optimizer.genetic_optimizer import GeneticOptimizerModule  # noqa: F401
from core.modules.bucket_optimizer.bucket_optimizer import BucketOptimizerModule  # noqa: F401
from core.modules.rpp_approximation.rpp_approximation import RPPApproximationModule  # noqa: F401


# ── Helpers ────────────────────────────────────────────────────────────────────


class Problem(TypedDict, total=True):
    name: str
    path: str
    settings: ProblemSettings


def _all_optimizer_classes() -> dict[str, type]:
    """Recursively discover all concrete (non-abstract) BaseOptimizer subclasses."""
    result: dict[str, type] = {}

    def _recurse(cls: type) -> None:
        for sub in cls.__subclasses__():
            if not inspect.isabstract(sub):
                result[sub.__name__] = sub
            _recurse(sub)

    _recurse(BaseOptimizer)
    return result


T = TypeVar("T")


def _get_constructor_params(
    cls: type, blacklist: Optional[list[str]] = None
) -> dict[str, Tuple[type[T], T]]:
    """Return {param_name: (annotation, default)} for __init__, excluding self."""
    if blacklist is None:
        blacklist = ["self"]
    else:
        blacklist.append("self")
    signature = inspect.signature(cls.__init__)
    try:
        hints = get_type_hints(cls.__init__)
    except Exception:
        hints = {}
    return {
        name: (hints[name], param.default)
        for name, param in signature.parameters.items()
        if name not in blacklist
    }


def _unwrap_optional(annotation: Union[type, Optional[type], type | None]) -> type:
    """Unwrap Optional[X] / X | None → X. Returns annotation unchanged otherwise."""
    origin = get_origin(annotation)
    args = get_args(annotation)
    is_union = origin is typing.Union or (
        hasattr(types, "UnionType") and isinstance(annotation, types.UnionType)
    )
    if is_union and args:
        non_none = [a for a in args if a is not type(None)]
        if non_none:
            return non_none[0]
    assert isinstance(annotation, type)
    return annotation


def _param_widget(label: str, annotation: type, default: Any, key: str) -> Any:
    """Render a Streamlit widget appropriate for the type; return the current value."""
    annotation = _unwrap_optional(annotation)
    has_default = default is not inspect.Parameter.empty

    if annotation is bool:
        return st.checkbox(
            label, value=bool(default) if has_default else False, key=key
        )
    elif annotation is int:
        return st.number_input(
            label, value=int(default) if has_default else 0, step=1, key=key
        )
    elif annotation is float:
        return st.number_input(
            label,
            value=float(default) if has_default else 0.0,
            step=0.1,
            format="%.4f",
            key=key,
        )
    else:
        with st.container(border=True):
            st.text(label)
            return annotation(
                *[
                    _param_widget(
                        f"{label}: {sub_name}", sub_type, sub_default, f"{key}_sub_{i}"
                    )
                    for i, (sub_name, (sub_type, sub_default)) in enumerate(
                        _get_constructor_params(annotation).items()
                    )
                ]
            )

    return None


def _default_settings() -> ProblemSettings:
    return ProblemSettings(
        material_height=6.0,
        dpi=72.0,
        nest_geometry=True,
        x_offset=0.0,
        y_offset=0.0,
        model_scale=1.0,
        feedrate=600,
    )


# ── Session State ──────────────────────────────────────────────────────────────


def _init_state() -> None:
    defaults: dict[str, Any] = {
        "problems": [],  # list of {name, path, settings: dict}
        "optimizers": [],  # list of (opt_name: str, type(Optimizer), params: dict)
        "base_optimizer": (BaseOptimizer.__name__, BaseOptimizer, {}),
        "sample_size": 5,
        "results": None,
        "total_cost": None,
        "tmp_dir": tempfile.mkdtemp(prefix="opt_suite_"),
    }

    for key, val in defaults.items():
        if key not in st.session_state:
            st.session_state[key] = val


# ── Problems Tab ───────────────────────────────────────────────────────────────


def _problems_tab() -> None:
    st.subheader("Load Problems")

    uploaded = st.file_uploader(
        "Drop SVG files here or click to browse",
        type=["svg"],
        accept_multiple_files=True,
    )

    if uploaded:
        existing = {p["name"] for p in st.session_state.problems}
        for f in uploaded:
            filename = str(f.name)
            if filename not in existing:
                path = os.path.join(str(st.session_state.tmp_dir), filename)
                with open(path, "wb") as out:
                    out.write(f.getbuffer())
                st.session_state.problems.append(
                    Problem(name=filename, path=path, settings=_default_settings())
                )

    if not st.session_state.problems:
        st.info("No SVGs loaded yet. Upload files above to get started.")
        return

    st.divider()
    st.subheader(f"Loaded Problems ({len(st.session_state.problems)})")

    to_remove: int | None = None

    for i, problem in enumerate(st.session_state.problems):
        with st.expander(f"📄 {problem['name']}"):
            s = cast(ProblemSettings, problem["settings"])
            c1, c2, c3 = st.columns(3)

            with c1:
                s.material_height = st.number_input(
                    "Material height",
                    value=s.material_height,
                    step=0.1,
                    format="%.2f",
                    key=f"mh_{i}",
                )
                s.dpi = st.number_input(
                    "DPI",
                    value=s.dpi,
                    step=1.0,
                    format="%.1f",
                    key=f"dpi_{i}",
                )
            with c2:
                s.feedrate = st.number_input(
                    "Feedrate", value=s.feedrate, step=1.0, format="%.0f", key=f"fr_{i}"
                )
                s.model_scale = st.number_input(
                    "Model scale",
                    value=s.model_scale,
                    step=0.1,
                    format="%.2f",
                    key=f"ms_{i}",
                )
            with c3:
                s.nest_geometry = st.checkbox(
                    "Nest geometry",
                    value=s.nest_geometry,
                    key=f"ng_{i}",
                )
                if s.nest_geometry:
                    s.x_offset = 0.0
                    s.y_offset = 0.0
                else:
                    s.x_offset = st.number_input(
                        "X offset",
                        value=s.x_offset,
                        step=0.1,
                        format="%.2f",
                        key=f"xo_{i}",
                    )
                    s.y_offset = st.number_input(
                        "Y offset",
                        value=s.y_offset,
                        step=0.1,
                        format="%.2f",
                        key=f"yo_{i}",
                    )

            if st.button("Remove", key=f"rm_{i}"):
                to_remove = i

    if to_remove is not None:
        st.session_state.problems.pop(to_remove)
        st.rerun()


# ── Optimizers Tab ─────────────────────────────────────────────────────────────


def _optimizers_tab() -> None:
    st.subheader("General Configurations")
    base_params: dict[str, Tuple[type, Any]] = _get_constructor_params(
        BaseOptimizer, ["material_height"]
    )
    if base_params:
        cols = st.columns(min(len(base_params), 4))
        for j, (parameter_name, (type_annotation, default_value)) in enumerate(
            base_params.items()
        ):
            stored_value = st.session_state.base_optimizer[2].get(
                parameter_name,
                default_value,
            )
            with cols[j % len(cols)]:
                val = _param_widget(
                    parameter_name,
                    type_annotation,
                    stored_value,
                    key=f"p_{BaseOptimizer.__name__}_{parameter_name}",
                )
                st.session_state.base_optimizer[2][parameter_name] = val
    st.divider()
    st.subheader("Select & Configure Optimizers")

    known_optimizers = _all_optimizer_classes()
    if not known_optimizers:
        st.warning(
            "No BaseOptimizer subclasses found. "
            "Add your optimizer imports at the top of app.py."
        )
        return

    for (index, (opt_name, cls)), col in zip(
        enumerate(known_optimizers.items()),
        st.columns([1] * len(known_optimizers) + [5]),
    ):
        with col:
            if st.button(opt_name, key=f"add_{opt_name}"):
                params: dict[str, Tuple[type, Any]] = _get_constructor_params(cls)
                index = len(st.session_state.optimizers)
                st.session_state.optimizers.append((opt_name, cls, dict()))

    swap: tuple[int, int] | None = None

    for index, (opt_name, cls, _) in enumerate(st.session_state.optimizers):
        params: dict[str, Tuple[type, Any]] = _get_constructor_params(
            cls, list(_get_constructor_params(BaseOptimizer).keys())
        )
        with st.container(border=True):
            del_col, name_col, up_col, dn_col = st.columns([0.4, 5, 0.4, 0.4])

            with del_col:
                if st.button("🗑", key=f"del_{opt_name}_{index}"):
                    st.session_state.optimizers.pop(index)
                    st.rerun()

            with name_col:
                st.markdown(f"***{opt_name}**")

            with up_col:
                if index > 0 and st.button("↑", key=f"up_{opt_name}_{index}"):
                    swap = (index, index - 1)

            with dn_col:
                if index < len(st.session_state.optimizers) - 1 and st.button(
                    "↓", key=f"dn_{opt_name}_{index}"
                ):
                    swap = (index, index + 1)

            if params:
                if len(st.session_state.optimizers) <= index:
                    st.session_state.optimizers.append((opt_name, cls, dict()))

                cols = st.columns(min(len(params), 4))
                for j, (parameter_name, (type_annotation, default_value)) in enumerate(
                    params.items()
                ):
                    stored_value = st.session_state.optimizers[index][2].get(
                        parameter_name,
                        default_value,
                    )
                    with cols[j % len(cols)]:
                        val = _param_widget(
                            parameter_name,
                            type_annotation,
                            stored_value,
                            key=f"p_{opt_name}_{parameter_name}_{index}",
                        )
                        st.session_state.optimizers[index][2][parameter_name] = val

    if swap:
        a, b = swap
        st.session_state.optimizers[a], st.session_state.optimizers[b] = (
            st.session_state.optimizers[b],
            st.session_state.optimizers[a],
        )
        st.rerun()


# ── Run Tab ────────────────────────────────────────────────────────────────────


def _run_tab() -> None:
    st.subheader("Run Configuration")

    st.session_state.sample_size = st.number_input(
        "Iterations per optimizer per problem",
        min_value=1,
        value=st.session_state.sample_size,
        step=1,
    )

    n_problems = len(st.session_state.problems)
    n_optimizers = len(st.session_state.optimizers)
    ready = n_problems > 0 and n_optimizers > 0

    if not ready:
        st.warning("Load at least one problem and enable at least one optimizer.")

    st.divider()

    if st.button("▶ Run Suite", type="primary", disabled=not ready):
        _execute_suite()

    if st.session_state.results is not None:
        st.divider()
        df: pd.DataFrame = st.session_state.results
        st.subheader("Original")
        originals = df[df["optimizer"] == "Original"][["svg_path", "travel_cost"]]
        originals["total_time"] = st.session_state.total_costs
        st.dataframe(originals, use_container_width=True)
        # for i, original in enumerate(originals):
        #     cols = st.columns(5)
        #     with cols[0]:
        #         a
        #         st.image(original["svg_path"])

        #     with cols[1]:
        #         st.text(f"Total time: {st.session_state.total_costs[i]:.3f}s")

        #     with cols[2]:
        #         st.text(f"Travel time: {df["travel_cost"]:.3f}s")

        st.subheader("Results")
        baseline = originals.rename(columns={"travel_cost": "original_cost"})
        df = df.merge(baseline, on="svg_path", how="left")
        df["cost_reduction"] = df["original_cost"] - df["travel_cost"]
        df["reduction_pct"] = df["cost_reduction"] / df["original_cost"] * 100
        stats = df.groupby(["svg_path", "optimizer"], sort=False)[
            [
                "travel_cost",
                "wall_clock_time_s",
                "process_time_s",
                "cost_reduction",
                "reduction_pct",
            ]
        ].agg(["mean", "std", "min", "max", "median"])
        st.dataframe(stats, use_container_width=True)


def _execute_suite() -> None:
    # Instantiate optimizers in the configured order, skipping disabled ones
    optimizers: list[Tuple[type[BaseOptimizer], dict[str, Any]]] = []
    for entry in st.session_state.optimizers:
        opt_class: type[BaseOptimizer] = entry[1]
        params: dict = entry[2]
        optimizers.append((opt_class, params))

    # Build the problems list expected by run_suite
    problems: list[Tuple[ProblemSettings, str]] = [
        (p["settings"], p["path"]) for p in st.session_state.problems
    ]

    # ── Progress display ──────────────────────────────────────────────────────
    n: int = st.session_state.sample_size
    # Original: 1 callback per problem; Randomized: n; each optimizer: n
    total_steps = len(problems) * (1 + n * (1 + len(optimizers)))
    progress_bar = st.progress(0.0, text="Starting…")
    log_area = st.empty()
    step = [0]
    recent: list[str] = []

    def on_progress(svg_path: str, optimizer_name: str, iteration: int) -> None:
        step[0] += 1
        frac = min(step[0] / total_steps, 1.0)
        short_name = Path(svg_path).name
        msg = f"{short_name}  ·  {optimizer_name}  ·  iter {iteration + 1}"
        progress_bar.progress(frac, text=msg)
        recent.append(msg)
        if len(recent) > 8:
            recent.pop(0)
        log_area.text("\n".join(recent))

    # ── Execute ───────────────────────────────────────────────────────────────
    try:
        df, total_costs = run_suite(
            on_progress=on_progress,
            problems=problems,
            optimizers=optimizers,
            sample_size=n,
        )
        st.session_state.results = df
        st.session_state.total_costs = total_costs
        progress_bar.progress(1.0, text="Done!")
        log_area.empty()
    except Exception as e:
        st.error(f"Suite failed: {e}")
        raise

    st.rerun()


# ── Entry Point ────────────────────────────────────────────────────────────────


def main() -> None:
    st.set_page_config(
        page_title="Path Optimization Suite",
        layout="wide",
    )
    st.title("Path Optimization Suite")

    _init_state()

    problems_tab, optimizers_tab, run_tab = st.tabs(
        ["📂 Problems", "🔧 Optimizers", "▶ Run"]
    )
    with problems_tab:
        _problems_tab()
    with optimizers_tab:
        _optimizers_tab()
    with run_tab:
        _run_tab()


if __name__ == "__main__":
    main()
