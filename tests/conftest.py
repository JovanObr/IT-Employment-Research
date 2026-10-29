"""Shared fixtures. Tests never touch the real data/ folder and never use the network.

`DATA_DIR` is pointed at a throw-away folder *before* any project module is imported (collectors.common reads
it at import time), and the `data_dir` fixture re-points every module that copied RAW/CACHE/PROCESSED.
"""
import os
import sys
import tempfile
from pathlib import Path

os.environ["DATA_DIR"] = tempfile.mkdtemp(prefix="it_research_tests_")
sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

import pytest  # noqa: E402


@pytest.fixture
def data_dir(tmp_path, monkeypatch):
    """A clean data/ tree in tmp_path, patched into every module that holds a copy of the path constants."""
    from collectors import common
    paths = {n: tmp_path / n.lower() for n in ("CACHE", "RAW", "PROCESSED", "MANUAL")}
    for p in paths.values():
        p.mkdir(parents=True, exist_ok=True)
    for name, p in paths.items():
        monkeypatch.setattr(common, name, p)
    import build_master
    import build_metro_panel
    for mod in (build_master, build_metro_panel):
        for name, p in paths.items():
            if hasattr(mod, name):
                monkeypatch.setattr(mod, name, p)
    for modname in ("collectors.sec", "collectors.fhfa", "collectors.hn", "collectors.qcew",
                    "collectors.eurostat", "collectors.census_gazetteer"):
        mod = sys.modules.get(modname)
        if mod is not None and hasattr(mod, "RAW"):
            monkeypatch.setattr(mod, "RAW", paths["RAW"])
    return tmp_path
