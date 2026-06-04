"""
Placement visualizer for the backend demo pipeline.

Renders the macro placement grid to a PNG. This is a headless (Agg backend) port
of the placement-layout drawing code in FYP.ipynb so it can run without Jupyter.
"""
from __future__ import annotations

from pathlib import Path
from typing import Dict

import matplotlib

# Force a non-interactive backend so this works on a headless server / CI.
matplotlib.use("Agg")
import matplotlib.patches as mpatches  # noqa: E402
import matplotlib.pyplot as plt  # noqa: E402

# Macro-type -> fill color (mirrors the notebook palette).
MACRO_COLORS = {
    "simple_rom": "#4A90D9",
    "simple_alu": "#E85D75",
}
DEFAULT_COLOR = "#888888"


def render_placement(
    placements: Dict[str, list],
    instance_type_map: Dict[str, str],
    H: int,
    W: int,
    out_path: str | Path,
    title: str = "Placement",
    metrics: dict | None = None,
) -> str:
    """
    Draw the placement as labeled rectangles on an H x W grid and save to out_path.

    Args:
        placements: dict inst_name -> [y, x, h, w] (grid coordinates)
        instance_type_map: dict inst_name -> macro_type
        H, W: grid height/width
        out_path: PNG output path
        title: figure title
        metrics: optional metrics dict; if given, an info box is drawn

    Returns:
        The output path as a string.
    """
    out_path = Path(out_path)
    out_path.parent.mkdir(parents=True, exist_ok=True)

    fig, ax = plt.subplots(1, 1, figsize=(10, 10))
    ax.set_xlim(0, W)
    ax.set_ylim(H, 0)  # invert Y so (0,0) is top-left, matching the notebook
    ax.set_aspect("equal")

    used_types = set()
    for inst_name, box in placements.items():
        y, x, h, w = box
        macro_type = instance_type_map.get(inst_name, "other")
        used_types.add(macro_type)
        color = MACRO_COLORS.get(macro_type, DEFAULT_COLOR)
        rect = mpatches.Rectangle(
            (x, y), w, h, linewidth=1.5, edgecolor="black", facecolor=color, alpha=0.85
        )
        ax.add_patch(rect)
        ax.text(
            x + w / 2.0, y + h / 2.0, inst_name,
            ha="center", va="center", fontsize=10, fontweight="bold",
        )

    if metrics:
        stats_lines = [title]
        if "hpwl" in metrics:
            stats_lines.append(f"HPWL: {metrics['hpwl']:.2f}")
        if "congestion_top10" in metrics:
            stats_lines.append(f"Congestion (top 10%): {metrics['congestion_top10']:.3f}")
        if "thermal_score" in metrics:
            stats_lines.append(f"Thermal score: {metrics['thermal_score']:.3f}")
        if "num_components" in metrics:
            stats_lines.append(f"Components: {metrics['num_components']}")
        ax.text(
            0.02, 0.98, "\n".join(stats_lines), transform=ax.transAxes,
            fontsize=11, verticalalignment="top",
            bbox=dict(boxstyle="round", facecolor="wheat", alpha=0.9), family="monospace",
        )

    legend = [
        mpatches.Patch(facecolor=MACRO_COLORS.get(t, DEFAULT_COLOR), edgecolor="black", label=t)
        for t in sorted(used_types)
    ]
    if legend:
        ax.legend(handles=legend, loc="upper right")

    ax.set_xlabel("Grid X")
    ax.set_ylabel("Grid Y")
    ax.set_title(title)
    plt.tight_layout()
    fig.savefig(out_path, dpi=120)
    plt.close(fig)
    return str(out_path)
