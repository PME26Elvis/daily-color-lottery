import json

from PIL import Image

from src.package_weekly_showcase import (
    generate_html,
    make_week_window,
    select_weekly_top_outputs,
)


def test_select_weekly_top_outputs_per_source(tmp_path, monkeypatch):
    monkeypatch.chdir(tmp_path)
    output_dir = tmp_path / "output" / "archive" / "2026-06-03" / "source-a"
    output_dir.mkdir(parents=True)
    rows = []
    for index, score in enumerate([10, 90, 30, 80, 50, 70], start=1):
        path = output_dir / f"{index}.jpg"
        Image.new("RGB", (8, 8), (index, index, index)).save(path)
        rows.append(
            {
                "run_date": "2026-06-03",
                "run_id": f"run-{index}",
                "source_path": "sources/source-a.jpg",
                "source_name": "source-a.jpg",
                "source_slug": "source-a",
                "style": f"style-{index}",
                "score": {"score": score},
                "output_path": path.relative_to(tmp_path).as_posix(),
            }
        )

    old_path = tmp_path / "output" / "archive" / "2026-05-20" / "source-a" / "old.jpg"
    old_path.parent.mkdir(parents=True)
    Image.new("RGB", (8, 8), (0, 0, 0)).save(old_path)
    old_row = {
        "run_date": "2026-05-20",
        "run_id": "old-run",
        "source_path": "sources/source-a.jpg",
        "source_name": "source-a.jpg",
        "source_slug": "source-a",
        "style": "old",
        "score": {"score": 100},
        "output_path": old_path.relative_to(tmp_path).as_posix(),
    }

    logs = tmp_path / "logs"
    logs.mkdir()
    (logs / "runs.jsonl").write_text(
        json.dumps({"run_date": "2026-06-03", "outputs": rows})
        + "\n"
        + json.dumps({"run_date": "2026-05-20", "outputs": [old_row]})
        + "\n",
        encoding="utf-8",
    )

    selected = select_weekly_top_outputs(
        logs / "runs.jsonl",
        tmp_path,
        make_week_window(7, today=__import__("datetime").date(2026, 6, 3)),
        max_per_source=5,
    )

    scores = [row["score"]["score"] for row in selected["sources/source-a.jpg"]]
    assert scores == [90, 80, 70, 50, 30]


def test_generate_html_embeds_base64_mp4(tmp_path):
    mp4 = tmp_path / "weekly-showcase.mp4"
    mp4.write_bytes(b"fake mp4")
    manifest = {
        "week": {"earliest": "2026-05-28", "today": "2026-06-03"},
        "source": {"name": "demo.jpg"},
        "outputs": [
            {
                "rank": 1,
                "score": 99.5,
                "style": "clean_bright",
                "run_date": "2026-06-03",
                "run_id": "run",
                "output_path": "output/archive/demo.jpg",
                "params": {"exposure": 0.1},
            }
        ],
    }

    html = generate_html(manifest, mp4)

    assert "data:video/mp4;base64," in html
    assert "ZmFrZSBtcDQ=" in html
    assert "weekly-showcase-manifest" in html
    assert "Score 99.50" in html
