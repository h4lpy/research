"""Paths to the research datasets, read directly from their canonical
location - never copied into app/, so there is one copy of the evidence."""

import pathlib

ROOT = pathlib.Path(__file__).resolve().parents[2]
DATASETS = ROOT / "experiments" / "datasets"

EEBA = DATASETS / "eeba4cf4-74fa-417e-86ba-bf4990fe4c03.jsonl"
C0B4 = DATASETS / "c0b4f2ea-e8d3-4d29-bf8c-25fca694f539.jsonl"
C0B4_WITH_FILE = DATASETS / "c0b4f2ea-e8d3-4d29-bf8c-25fca694f539_with_file.jsonl"
EA2C = ROOT / "ea2c0634-0eb0-4923-94be-78a3e4236710.jsonl"


def read(path: pathlib.Path) -> str:
    return path.read_text(encoding="utf-8")
