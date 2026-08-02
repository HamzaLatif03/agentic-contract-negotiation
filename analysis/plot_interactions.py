#!/usr/bin/env python3
"""Generate report plots from results/interactions.json.

Usage (from repo root, with loan-negotiation env active):

    python analysis/plot_interactions.py
    python analysis/plot_interactions.py --input results/interactions.json --out analysis/figures
"""

from __future__ import annotations

import argparse
import json
import re
from pathlib import Path

import matplotlib.pyplot as plt
import numpy as np
import pandas as pd
import seaborn as sns

_REPO_ROOT = Path(__file__).resolve().parents[1]
_DEFAULT_INPUT = _REPO_ROOT / "results" / "interactions.json"
_DEFAULT_OUT = Path(__file__).resolve().parent / "figures"

_MODEL_LABELS = {
    "llama3.2:latest": "Llama 3.2",
    "ollama-local": "Llama 3.2",
    "gemini-3.1-flash-lite": "Gemini Flash Lite",
    "mistral-small": "Mistral Small",
}

_MODEL_ORDER = ["Llama 3.2", "Gemini Flash Lite", "Mistral Small"]
_MODEL_COLORS = {
    "Llama 3.2": "#1f4e79",
    "Gemini Flash Lite": "#2a9d8f",
    "Mistral Small": "#c45c26",
}


def _style() -> None:
    sns.set_theme(
        style="whitegrid",
        context="paper",
        font_scale=1.05,
        rc={
            "axes.edgecolor": "#333333",
            "axes.labelcolor": "#222222",
            "xtick.color": "#333333",
            "ytick.color": "#333333",
            "text.color": "#222222",
            "grid.color": "#dddddd",
            "figure.facecolor": "white",
            "axes.facecolor": "white",
            "font.family": "sans-serif",
        },
    )
    # Avoid default purple-heavy palettes.
    sns.set_palette(["#1f4e79", "#2a9d8f", "#c45c26", "#6c757d"])


def load_interactions(path: Path) -> pd.DataFrame:
    raw = json.loads(path.read_text(encoding="utf-8"))
    rows = raw.get("interactions", raw if isinstance(raw, list) else [])
    flat: list[dict] = []
    for row in rows:
        deal = row.get("deal") or {}
        reasons = row.get("reasons") or []
        reason_text = " | ".join(str(r) for r in reasons).lower()
        flat.append(
            {
                "id": row.get("id"),
                "timestamp": row.get("timestamp"),
                "model_id": row.get("model_id"),
                "model": _MODEL_LABELS.get(row.get("model_id", ""), row.get("model_id")),
                "persona_id": row.get("persona_id") or "unknown",
                "persona_name": row.get("persona_name") or row.get("persona_id") or "unknown",
                "status": row.get("status"),
                "rounds": row.get("rounds"),
                "borrower_score": row.get("borrower_score"),
                "lender_score": row.get("lender_score"),
                "score_gap": row.get("score_gap"),
                "consensus_reached": bool(row.get("consensus_reached")),
                "prompt_tokens": row.get("prompt_tokens"),
                "completion_tokens": row.get("completion_tokens"),
                "total_tokens": row.get("total_tokens"),
                "duration_s": (row.get("duration_ms") or 0) / 1000.0,
                "ttft_s": (
                    (row.get("ttft_ms") / 1000.0) if row.get("ttft_ms") is not None else None
                ),
                "middleman": bool(
                    re.search(r"middleman|ratif", reason_text)
                    or ("notes" in row and "middleman" in str(row.get("notes", "")).lower())
                ),
                "downpayment": deal.get("downpayment"),
                "interest_rate_pct": deal.get("interest_rate_pct"),
                "arrangement_fee": deal.get("arrangement_fee"),
                "cashback": deal.get("cashback"),
                "erc_pct": deal.get("erc_pct"),
                "rate_type": deal.get("rate_type"),
            }
        )
    df = pd.DataFrame(flat)
    if "model" in df.columns:
        df["model"] = pd.Categorical(df["model"], categories=_MODEL_ORDER, ordered=True)
    return df


def _save(fig: plt.Figure, out_dir: Path, name: str) -> Path:
    out_dir.mkdir(parents=True, exist_ok=True)
    path = out_dir / f"{name}.png"
    fig.tight_layout()
    fig.savefig(path, dpi=160, bbox_inches="tight")
    plt.close(fig)
    print(f"Wrote {path}")
    return path


def _negotiated(df: pd.DataFrame) -> pd.DataFrame:
    """Exclude impossible / failed pre-negotiation controls."""
    return df[df["status"] != "impossible"].copy()


def plot_mean_tokens_by_model(df: pd.DataFrame, out_dir: Path) -> None:
    data = _negotiated(df)
    means = data.groupby("model", observed=True)["total_tokens"].mean().reindex(_MODEL_ORDER)
    fig, ax = plt.subplots(figsize=(7, 4.2))
    means.plot(kind="bar", ax=ax, color=["#1f4e79", "#2a9d8f", "#c45c26"], width=0.7)
    ax.set_title("Mean total tokens by model")
    ax.set_xlabel("")
    ax.set_ylabel("Tokens")
    ax.tick_params(axis="x", rotation=0)
    for i, v in enumerate(means):
        if pd.notna(v):
            ax.text(i, v, f"{int(v):,}", ha="center", va="bottom", fontsize=9)
    _save(fig, out_dir, "01_mean_tokens_by_model")


def plot_mean_duration_by_model(df: pd.DataFrame, out_dir: Path) -> None:
    data = _negotiated(df)
    means = data.groupby("model", observed=True)["duration_s"].mean().reindex(_MODEL_ORDER)
    fig, ax = plt.subplots(figsize=(7, 4.2))
    means.plot(kind="bar", ax=ax, color=["#1f4e79", "#2a9d8f", "#c45c26"], width=0.7)
    ax.set_title("Mean wall-clock duration by model")
    ax.set_xlabel("")
    ax.set_ylabel("Seconds")
    ax.tick_params(axis="x", rotation=0)
    for i, v in enumerate(means):
        if pd.notna(v):
            ax.text(i, v, f"{v:.0f}s", ha="center", va="bottom", fontsize=9)
    _save(fig, out_dir, "02_mean_duration_by_model")


def plot_mean_ttft_by_model(df: pd.DataFrame, out_dir: Path) -> None:
    data = _negotiated(df).dropna(subset=["ttft_s"])
    means = data.groupby("model", observed=True)["ttft_s"].mean().reindex(_MODEL_ORDER)
    fig, ax = plt.subplots(figsize=(7, 4.2))
    means.plot(kind="bar", ax=ax, color=["#1f4e79", "#2a9d8f", "#c45c26"], width=0.7)
    ax.set_title("Mean time to first model output (TTFT)")
    ax.set_xlabel("")
    ax.set_ylabel("Seconds")
    ax.tick_params(axis="x", rotation=0)
    for i, v in enumerate(means):
        if pd.notna(v):
            ax.text(i, v, f"{v:.1f}s", ha="center", va="bottom", fontsize=9)
    _save(fig, out_dir, "03_mean_ttft_by_model")


def plot_rounds_boxplot(df: pd.DataFrame, out_dir: Path) -> None:
    data = _negotiated(df).dropna(subset=["rounds"])
    fig, ax = plt.subplots(figsize=(7, 4.2))
    # dodge=False keeps box + strip aligned when hue matches x (seaborn default offsets them).
    sns.boxplot(
        data=data,
        x="model",
        y="rounds",
        hue="model",
        order=_MODEL_ORDER,
        hue_order=_MODEL_ORDER,
        ax=ax,
        palette=_MODEL_COLORS,
        legend=False,
        dodge=False,
        width=0.5,
        showfliers=False,
    )
    sns.stripplot(
        data=data,
        x="model",
        y="rounds",
        hue="model",
        order=_MODEL_ORDER,
        hue_order=_MODEL_ORDER,
        ax=ax,
        palette=["#222222"] * len(_MODEL_ORDER),
        size=4,
        alpha=0.45,
        dodge=False,
        jitter=0.15,
        legend=False,
        zorder=3,
        edgecolor="white",
        linewidth=0.35,
    )
    ax.set_title("Negotiation rounds by model")
    ax.set_xlabel("")
    ax.set_ylabel("Rounds")
    lo = int(data["rounds"].min())
    hi = int(data["rounds"].max())
    ax.set_ylim(lo - 0.5, hi + 0.5)
    ax.set_yticks(range(lo, hi + 1))
    _save(fig, out_dir, "04_rounds_boxplot_by_model")


def plot_score_gap_boxplot(df: pd.DataFrame, out_dir: Path) -> None:
    data = _negotiated(df).dropna(subset=["score_gap"])
    fig, ax = plt.subplots(figsize=(7, 4.2))
    sns.boxplot(
        data=data,
        x="model",
        y="score_gap",
        hue="model",
        order=_MODEL_ORDER,
        hue_order=_MODEL_ORDER,
        ax=ax,
        palette=_MODEL_COLORS,
        legend=False,
        dodge=False,
        width=0.5,
    )
    ax.axhline(2.0, color="#888888", linestyle="--", linewidth=1, label="Max gap = 2")
    ax.set_title("Fairness score gap by model")
    ax.set_xlabel("")
    ax.set_ylabel("|borrower − lender| score")
    ax.legend(frameon=False)
    _save(fig, out_dir, "05_score_gap_boxplot_by_model")


def plot_score_scatter(df: pd.DataFrame, out_dir: Path) -> None:
    data = _negotiated(df).dropna(subset=["borrower_score", "lender_score"])
    fig, ax = plt.subplots(figsize=(6.5, 5.5))
    for model, color in zip(
        _MODEL_ORDER, ["#1f4e79", "#2a9d8f", "#c45c26"], strict=False
    ):
        subset = data[data["model"] == model]
        ax.scatter(
            subset["borrower_score"],
            subset["lender_score"],
            label=model,
            alpha=0.75,
            s=45,
            c=color,
            edgecolors="white",
            linewidths=0.4,
        )
    ax.plot([1, 10], [1, 10], color="#999999", linestyle="--", linewidth=1)
    ax.set_xlim(1, 10)
    ax.set_ylim(1, 10)
    ax.set_xlabel("Borrower score")
    ax.set_ylabel("Lender score")
    ax.set_title("Party scores (diagonal = equal)")
    ax.legend(frameon=False)
    _save(fig, out_dir, "06_score_scatter_by_model")


def plot_rounds_heatmap(df: pd.DataFrame, out_dir: Path) -> None:
    data = _negotiated(df).dropna(subset=["rounds"])
    pivot = (
        data.pivot_table(
            index="persona_name",
            columns="model",
            values="rounds",
            aggfunc="mean",
            observed=True,
        )
        .reindex(columns=_MODEL_ORDER)
    )
    fig, ax = plt.subplots(figsize=(8.5, 6))
    sns.heatmap(
        pivot,
        annot=True,
        fmt=".1f",
        cmap="YlOrBr",
        ax=ax,
        linewidths=0.5,
        cbar_kws={"label": "Mean rounds"},
    )
    ax.set_title("Mean negotiation rounds by persona × model")
    ax.set_xlabel("")
    ax.set_ylabel("")
    _save(fig, out_dir, "07_rounds_heatmap_persona_model")


def plot_tokens_heatmap(df: pd.DataFrame, out_dir: Path) -> None:
    data = _negotiated(df).dropna(subset=["total_tokens"])
    pivot = (
        data.pivot_table(
            index="persona_name",
            columns="model",
            values="total_tokens",
            aggfunc="mean",
            observed=True,
        )
        .reindex(columns=_MODEL_ORDER)
    )
    fig, ax = plt.subplots(figsize=(8.5, 6))
    sns.heatmap(
        pivot / 1000.0,
        annot=True,
        fmt=".0f",
        cmap="YlGnBu",
        ax=ax,
        linewidths=0.5,
        cbar_kws={"label": "Mean tokens (thousands)"},
    )
    ax.set_title("Mean total tokens (×1000) by persona × model")
    ax.set_xlabel("")
    ax.set_ylabel("")
    _save(fig, out_dir, "08_tokens_heatmap_persona_model")


def plot_middleman_rate(df: pd.DataFrame, out_dir: Path) -> None:
    data = _negotiated(df)
    rates = (
        data.groupby("model", observed=True)["middleman"]
        .mean()
        .reindex(_MODEL_ORDER)
        .fillna(0)
        * 100
    )
    fig, ax = plt.subplots(figsize=(7, 4.2))
    rates.plot(kind="bar", ax=ax, color=["#1f4e79", "#2a9d8f", "#c45c26"], width=0.7)
    ax.set_title("Middleman / ratification intervention rate")
    ax.set_xlabel("")
    ax.set_ylabel("% of negotiated runs")
    ax.set_ylim(0, 100)
    ax.tick_params(axis="x", rotation=0)
    for i, v in enumerate(rates):
        ax.text(i, v, f"{v:.0f}%", ha="center", va="bottom", fontsize=9)
    _save(fig, out_dir, "09_middleman_rate_by_model")


def plot_status_counts(df: pd.DataFrame, out_dir: Path) -> None:
    counts = (
        df.groupby(["model", "status"], observed=True)
        .size()
        .unstack(fill_value=0)
        .reindex(index=_MODEL_ORDER)
    )
    fig, ax = plt.subplots(figsize=(7.5, 4.5))
    counts.plot(kind="bar", stacked=True, ax=ax, width=0.75)
    ax.set_title("Run outcomes by model")
    ax.set_xlabel("")
    ax.set_ylabel("Count")
    ax.tick_params(axis="x", rotation=0)
    ax.legend(title="status", frameon=False)
    _save(fig, out_dir, "10_status_counts_by_model")


def plot_tokens_vs_rounds(df: pd.DataFrame, out_dir: Path) -> None:
    data = _negotiated(df).dropna(subset=["rounds", "total_tokens"])
    fig, ax = plt.subplots(figsize=(7, 5))
    for model, color in zip(
        _MODEL_ORDER, ["#1f4e79", "#2a9d8f", "#c45c26"], strict=False
    ):
        subset = data[data["model"] == model]
        ax.scatter(
            subset["rounds"],
            subset["total_tokens"],
            label=model,
            alpha=0.75,
            s=45,
            c=color,
            edgecolors="white",
            linewidths=0.4,
        )
    ax.set_xlabel("Rounds")
    ax.set_ylabel("Total tokens")
    ax.set_title("Tokens vs negotiation rounds")
    ax.legend(frameon=False)
    _save(fig, out_dir, "11_tokens_vs_rounds")


def _persona_order(data: pd.DataFrame) -> list[str]:
    """Stable persona axis: prefer demo first, then alphabetical."""
    names = sorted(data["persona_name"].dropna().unique().tolist())
    if "Demo" in names:
        names.remove("Demo")
        names = ["Demo", *names]
    return names


def _line_by_persona(
    data: pd.DataFrame,
    *,
    value: str,
    title: str,
    ylabel: str,
    out_name: str,
    out_dir: Path,
    scale: float = 1.0,
) -> None:
    personas = _persona_order(data)
    fig, ax = plt.subplots(figsize=(10, 4.8))
    x = np.arange(len(personas))
    for model in _MODEL_ORDER:
        subset = data[data["model"] == model]
        means = (
            subset.groupby("persona_name", observed=True)[value]
            .mean()
            .reindex(personas)
            * scale
        )
        ax.plot(
            x,
            means.values,
            marker="o",
            linewidth=2,
            markersize=5,
            label=model,
            color=_MODEL_COLORS[model],
        )
    ax.set_xticks(x)
    ax.set_xticklabels(personas, rotation=35, ha="right")
    ax.set_title(title)
    ax.set_ylabel(ylabel)
    ax.set_xlabel("")
    ax.legend(frameon=False)
    _save(fig, out_dir, out_name)


def plot_rounds_line_by_persona(df: pd.DataFrame, out_dir: Path) -> None:
    data = _negotiated(df).dropna(subset=["rounds"])
    _line_by_persona(
        data,
        value="rounds",
        title="Mean negotiation rounds by persona (line = model)",
        ylabel="Mean rounds",
        out_name="13_rounds_line_by_persona",
        out_dir=out_dir,
    )


def plot_tokens_line_by_persona(df: pd.DataFrame, out_dir: Path) -> None:
    data = _negotiated(df).dropna(subset=["total_tokens"])
    _line_by_persona(
        data,
        value="total_tokens",
        title="Mean total tokens by persona (line = model)",
        ylabel="Mean tokens (thousands)",
        out_name="14_tokens_line_by_persona",
        out_dir=out_dir,
        scale=1 / 1000.0,
    )


def plot_score_gap_line_by_persona(df: pd.DataFrame, out_dir: Path) -> None:
    data = _negotiated(df).dropna(subset=["score_gap"])
    personas = _persona_order(data)
    fig, ax = plt.subplots(figsize=(10, 4.8))
    x = np.arange(len(personas))
    for model in _MODEL_ORDER:
        subset = data[data["model"] == model]
        means = (
            subset.groupby("persona_name", observed=True)["score_gap"]
            .mean()
            .reindex(personas)
        )
        ax.plot(
            x,
            means.values,
            marker="o",
            linewidth=2,
            markersize=5,
            label=model,
            color=_MODEL_COLORS[model],
        )
    ax.axhline(2.0, color="#888888", linestyle="--", linewidth=1, label="Max gap = 2")
    ax.set_xticks(x)
    ax.set_xticklabels(personas, rotation=35, ha="right")
    ax.set_title("Mean fairness score gap by persona")
    ax.set_ylabel("Mean |borrower − lender|")
    ax.set_xlabel("")
    ax.legend(frameon=False)
    _save(fig, out_dir, "15_score_gap_line_by_persona")


def plot_duration_line_by_persona(df: pd.DataFrame, out_dir: Path) -> None:
    data = _negotiated(df).dropna(subset=["duration_s"])
    _line_by_persona(
        data,
        value="duration_s",
        title="Mean duration by persona (line = model)",
        ylabel="Mean seconds",
        out_name="16_duration_line_by_persona",
        out_dir=out_dir,
    )


def plot_cumulative_tokens_over_runs(df: pd.DataFrame, out_dir: Path) -> None:
    """Chronological cumulative token spend per model (shows cost growth)."""
    data = _negotiated(df).dropna(subset=["total_tokens", "timestamp"]).copy()
    data["timestamp"] = pd.to_datetime(data["timestamp"], utc=True)
    data = data.sort_values("timestamp")
    fig, ax = plt.subplots(figsize=(9, 4.8))
    for model in _MODEL_ORDER:
        subset = data[data["model"] == model].copy()
        if subset.empty:
            continue
        subset["run_index"] = np.arange(1, len(subset) + 1)
        subset["cum_tokens"] = subset["total_tokens"].cumsum() / 1000.0
        ax.plot(
            subset["run_index"],
            subset["cum_tokens"],
            marker="o",
            markersize=3.5,
            linewidth=2,
            label=model,
            color=_MODEL_COLORS[model],
        )
    ax.set_title("Cumulative tokens over successive negotiated runs")
    ax.set_xlabel("Run index (chronological, per model)")
    ax.set_ylabel("Cumulative tokens (thousands)")
    ax.legend(frameon=False)
    _save(fig, out_dir, "17_cumulative_tokens_over_runs")


def plot_max_round_rate_line(df: pd.DataFrame, out_dir: Path) -> None:
    """% of runs that hit the 10-round ceiling, by persona."""
    data = _negotiated(df).dropna(subset=["rounds"]).copy()
    data["hit_max"] = data["rounds"] >= 10
    personas = _persona_order(data)
    fig, ax = plt.subplots(figsize=(10, 4.8))
    x = np.arange(len(personas))
    for model in _MODEL_ORDER:
        subset = data[data["model"] == model]
        rates = (
            subset.groupby("persona_name", observed=True)["hit_max"]
            .mean()
            .reindex(personas)
            .fillna(0)
            * 100
        )
        ax.plot(
            x,
            rates.values,
            marker="o",
            linewidth=2,
            markersize=5,
            label=model,
            color=_MODEL_COLORS[model],
        )
    ax.set_xticks(x)
    ax.set_xticklabels(personas, rotation=35, ha="right")
    ax.set_ylim(0, 105)
    ax.set_title("% of runs hitting max rounds (≥10)")
    ax.set_ylabel("% of persona runs")
    ax.set_xlabel("")
    ax.legend(frameon=False)
    _save(fig, out_dir, "18_max_round_hit_rate_line")


def verify_accuracy(df: pd.DataFrame) -> None:
    """Recompute key aggregates and fail loudly if plot inputs look inconsistent."""
    data = _negotiated(df)
    print("\nAccuracy check (negotiated runs only):")
    issues: list[str] = []

    # score_gap must match |borrower - lender|
    scored = data.dropna(subset=["borrower_score", "lender_score", "score_gap"])
    for _, row in scored.iterrows():
        expected = round(abs(float(row["borrower_score"]) - float(row["lender_score"])), 1)
        if abs(float(row["score_gap"]) - expected) > 1e-6:
            issues.append(
                f"score_gap mismatch id={row['id']}: stored={row['score_gap']} expected={expected}"
            )

    # Balanced design: 3 models × 9 personas for negotiated set
    for model in _MODEL_ORDER:
        subset = data[data["model"] == model]
        n = len(subset)
        personas = subset["persona_id"].nunique()
        print(
            f"  {model}: n={n}, personas={personas}, "
            f"mean_rounds={subset['rounds'].mean():.3f}, "
            f"mean_tokens={subset['total_tokens'].mean():.1f}, "
            f"middleman%={100 * subset['middleman'].mean():.1f}"
        )
        if n != 27:
            issues.append(f"{model}: expected 27 negotiated runs, got {n}")
        if personas != 9:
            issues.append(f"{model}: expected 9 personas, got {personas}")

    impossible = df[df["status"] == "impossible"]
    print(f"  impossible controls: {len(impossible)} (excluded from metric plots)")
    if len(impossible) != 3:
        issues.append(f"expected 3 impossible rows, got {len(impossible)}")

    if issues:
        raise SystemExit("Accuracy check failed:\n- " + "\n- ".join(issues))
    print("  OK — aggregates consistent with interactions.json\n")


def write_summary_csv(df: pd.DataFrame, out_dir: Path) -> None:
    data = _negotiated(df)
    summary = (
        data.groupby("model", observed=True)
        .agg(
            n=("id", "count"),
            mean_rounds=("rounds", "mean"),
            mean_tokens=("total_tokens", "mean"),
            mean_duration_s=("duration_s", "mean"),
            mean_ttft_s=("ttft_s", "mean"),
            mean_score_gap=("score_gap", "mean"),
            middleman_pct=("middleman", "mean"),
            max_round_hit_pct=("rounds", lambda s: 100 * (s >= 10).mean()),
        )
        .reindex(_MODEL_ORDER)
    )
    summary["middleman_pct"] = summary["middleman_pct"] * 100
    out_dir.mkdir(parents=True, exist_ok=True)
    path = out_dir / "summary_by_model.csv"
    summary.to_csv(path, float_format="%.3f")
    print(f"Wrote {path}")


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--input",
        type=Path,
        default=_DEFAULT_INPUT,
        help="Path to interactions.json",
    )
    parser.add_argument(
        "--out",
        type=Path,
        default=_DEFAULT_OUT,
        help="Output directory for PNG figures",
    )
    parser.add_argument(
        "--skip-verify",
        action="store_true",
        help="Skip the built-in accuracy check",
    )
    args = parser.parse_args()

    if not args.input.exists():
        raise SystemExit(f"Input not found: {args.input}")

    _style()
    df = load_interactions(args.input)
    print(f"Loaded {len(df)} interactions from {args.input}")
    if not args.skip_verify:
        verify_accuracy(df)

    plot_mean_tokens_by_model(df, args.out)
    plot_mean_duration_by_model(df, args.out)
    plot_mean_ttft_by_model(df, args.out)
    plot_rounds_boxplot(df, args.out)
    plot_score_gap_boxplot(df, args.out)
    plot_score_scatter(df, args.out)
    plot_rounds_heatmap(df, args.out)
    plot_tokens_heatmap(df, args.out)
    plot_middleman_rate(df, args.out)
    plot_status_counts(df, args.out)
    plot_tokens_vs_rounds(df, args.out)
    plot_rounds_line_by_persona(df, args.out)
    plot_tokens_line_by_persona(df, args.out)
    plot_score_gap_line_by_persona(df, args.out)
    plot_duration_line_by_persona(df, args.out)
    plot_cumulative_tokens_over_runs(df, args.out)
    plot_max_round_rate_line(df, args.out)
    write_summary_csv(df, args.out)
    print(f"Done. Figures in {args.out.resolve()}")


if __name__ == "__main__":
    main()
