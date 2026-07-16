#!/usr/bin/env python3
"""
Bar plot of MassIVE datasets deposited per year, from datasets.csv.

Run massive_usis.py first to produce the CSV.

Install deps:
    pip install pandas matplotlib
"""

import argparse
import os

import pandas as pd
import matplotlib

matplotlib.use("Agg")
import matplotlib.pyplot as plt

SURFACE = "#fcfcfb"
SERIES = "#2a78d6"
INK = "#1a1a19"
INK_MUTED = "#6b6b68"
GRID = "#e5e5e2"


def plot(df, keyword, out_path, freq):
    dates = pd.to_datetime(df["deposition_date"], errors="coerce").dropna()
    if dates.empty:
        raise SystemExit("No usable deposition dates in the CSV.")

    # Reindex over the full span so empty periods show as zero-height bars. A
    # value_counts alone drops them, which silently compresses the time axis.
    if freq == "year":
        years = dates.dt.year
        counts = years.value_counts().reindex(range(years.min(), years.max() + 1), fill_value=0).sort_index()
        labels = [str(i) for i in counts.index]
        xlabel = "Year of deposition"
    else:
        periods = dates.dt.to_period("Q")
        full = pd.period_range(periods.min(), periods.max(), freq="Q")
        counts = periods.value_counts().reindex(full, fill_value=0).sort_index()
        labels = [str(p) for p in counts.index]
        xlabel = "Quarter of deposition"

    # The current period is still accruing; flag it rather than let it read as a decline.
    now = pd.Timestamp.now()
    current = now.year if freq == "year" else pd.Period(now, freq="Q")
    partial_idx = list(counts.index).index(current) if current in list(counts.index) else None

    fig, ax = plt.subplots(figsize=(9, 4.5), facecolor=SURFACE)
    ax.set_facecolor(SURFACE)

    # 2px surface gap between adjacent bars: width < 1 leaves the gap at any figure size.
    bars = ax.bar(range(len(counts)), counts.values, width=0.72, color=SERIES, zorder=3)

    # Hatch, not a second hue: the partial period is the same series, marked as incomplete.
    if partial_idx is not None:
        bars[partial_idx].set_hatch("///")
        bars[partial_idx].set_edgecolor(SURFACE)
        bars[partial_idx].set_linewidth(0)
        labels[partial_idx] += "\n(partial)"

    for rect, value in zip(bars, counts.values):
        ax.annotate(
            str(value),
            (rect.get_x() + rect.get_width() / 2, rect.get_height()),
            xytext=(0, 3),
            textcoords="offset points",
            ha="center",
            va="bottom",
            fontsize=9,
            color=INK_MUTED,
        )

    ax.set_title(
        f"MassIVE datasets deposited per {freq}, keyword '{keyword}'  (n={int(counts.sum())})",
        fontsize=12,
        color=INK,
        pad=26,
        loc="left",
    )
    ax.set_xlabel(xlabel, fontsize=10, color=INK_MUTED, labelpad=8)
    ax.set_ylabel("Datasets", fontsize=10, color=INK_MUTED, labelpad=8)
    ax.set_xticks(range(len(counts)))
    ax.set_xticklabels(labels, rotation=0 if freq == "year" else 45, ha="center" if freq == "year" else "right")
    if partial_idx is not None:
        ax.annotate(
            f"Hatched bar is incomplete: {now:%Y-%m-%d}",
            xy=(0, 1),
            xycoords="axes fraction",
            xytext=(0, 8),
            textcoords="offset points",
            fontsize=8.5,
            color=INK_MUTED,
        )

    ax.yaxis.grid(True, color=GRID, linewidth=1, zorder=0)
    ax.set_axisbelow(True)
    ax.xaxis.grid(False)
    for side in ("top", "right", "left"):
        ax.spines[side].set_visible(False)
    ax.spines["bottom"].set_color(GRID)
    ax.tick_params(colors=INK_MUTED, length=0)
    # Headroom so the tallest bar's value label doesn't collide with the title.
    ax.set_ylim(0, counts.max() * 1.15)

    fig.tight_layout()
    fig.savefig(out_path, dpi=200, facecolor=SURFACE)
    print(f"Wrote {out_path}")

    table = out_path.rsplit(".", 1)[0] + "_table.csv"
    counts.rename("datasets").rename_axis(freq).to_csv(table)
    print(f"Wrote {table}")


def main():
    here = os.path.dirname(os.path.abspath(__file__))
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--csv", default=os.path.join(here, "output", "datasets.csv"))
    ap.add_argument("--out", default=os.path.join(here, "output", "depositions_over_time.png"))
    ap.add_argument("--keyword", default="mscollaboratory")
    ap.add_argument("--freq", choices=["year", "quarter"], default="year")
    args = ap.parse_args()

    plot(pd.read_csv(args.csv), args.keyword, args.out, args.freq)


if __name__ == "__main__":
    main()
