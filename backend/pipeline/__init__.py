"""
Backend demo pipeline package for the ACFRL AI-driven chip floorplanning FYP.

This package wraps the placement flow that currently lives in FYP.ipynb so it can
be run headlessly (no Jupyter) from the repo root.

Public entry point:
    from backend.pipeline.full_pipeline import run_pipeline

Modules:
    full_pipeline  - orchestrates parse -> placement -> metrics -> DEF -> PNG
    metrics        - HPWL / congestion / thermal scoring (extracted from notebook)
    visualizer     - renders the placement layout to a PNG
"""

from .full_pipeline import run_pipeline  # noqa: F401

__all__ = ["run_pipeline"]
