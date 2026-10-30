"""collect.py must merge into data/manifest.json, not overwrite it (a partial run used to wipe the other entries)."""
import json
import sys

import collect


def entry(file, source="s", at="t1"):
    return {"source": source, "file": file, "url": "u", "licence_or_terms": "l", "retrieved_at_utc": at}


def test_merge_keeps_old_entries_and_replaces_rerun_ones():
    old = [entry("data/raw/a.csv", at="old"), entry("data/raw/b.csv", at="old")]
    new = [entry("data/raw/b.csv", at="new"), entry("data/raw/c.csv", at="new")]
    out = collect.merge_manifest(old, new)
    assert [e["file"] for e in out] == ["data/raw/a.csv", "data/raw/b.csv", "data/raw/c.csv"]
    assert {e["file"]: e["retrieved_at_utc"] for e in out} == {"data/raw/a.csv": "old", "data/raw/b.csv": "new", "data/raw/c.csv": "new"}


def test_merge_treats_windows_and_posix_paths_as_the_same_file():
    out = collect.merge_manifest([entry("data\\raw\\a.csv", at="old")], [entry("data/raw/a.csv", at="new")])
    assert len(out) == 1 and out[0]["retrieved_at_utc"] == "new"


def test_merge_with_nothing_new_keeps_everything():
    old = [entry("data/raw/a.csv")]
    assert collect.merge_manifest(old, []) == old


def test_partial_run_does_not_wipe_the_manifest(data_dir, monkeypatch):
    raw = data_dir / "raw"
    monkeypatch.setattr(collect, "RAW", raw)
    manifest = data_dir / "manifest.json"
    manifest.write_text(json.dumps([entry("data/raw/old.csv", at="old")]))
    monkeypatch.setattr(collect, "SOURCES", {"fake": lambda a: [entry("data/raw/new.csv", at="new")]})
    monkeypatch.setattr(sys, "argv", ["collect.py", "--sources", "fake"])
    collect.main()
    files = [e["file"] for e in json.loads(manifest.read_text())]
    assert files == ["data/raw/old.csv", "data/raw/new.csv"]


def test_unreadable_manifest_is_replaced_not_fatal(data_dir, monkeypatch):
    monkeypatch.setattr(collect, "RAW", data_dir / "raw")
    (data_dir / "manifest.json").write_text("{not json")
    monkeypatch.setattr(collect, "SOURCES", {"fake": lambda a: [entry("data/raw/new.csv")]})
    monkeypatch.setattr(sys, "argv", ["collect.py", "--sources", "fake"])
    collect.main()
    assert [e["file"] for e in json.loads((data_dir / "manifest.json").read_text())] == ["data/raw/new.csv"]
