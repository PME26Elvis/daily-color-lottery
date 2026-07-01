
from src.analytics import build_style_analytics, read_compacted_runs, write_style_analytics
from src.utils import append_jsonl


def output(style, score, run_date, path, source_win=False):
    return {
        "style": style,
        "run_date": run_date,
        "output_path": path,
        "score": {"score": score},
        "best_for_source_today": source_win,
    }


def test_build_style_analytics_groups_scores_and_wins():
    runs = [
        {
            "run_id": "run-1",
            "run_date": "2026-06-20",
            "best_output": {"output_path": "a-1"},
            "outputs": [
                output("warm", 90, "2026-06-20", "a-1", source_win=True),
                output("cool", 70, "2026-06-20", "a-2"),
            ],
        },
        {
            "run_id": "run-2",
            "run_date": "2026-06-30",
            "best_output": {"output_path": "b-2"},
            "outputs": [
                output("warm", 80, "2026-06-30", "b-1"),
                output("cool", 100, "2026-06-30", "b-2", source_win=True),
            ],
        },
    ]

    analytics = build_style_analytics(runs)

    by_style = {row["style"]: row for row in analytics["styles"]}
    assert analytics["run_count"] == 2
    assert analytics["output_count"] == 4
    assert analytics["latest_run_date"] == "2026-06-30"
    assert by_style["warm"]["count"] == 2
    assert by_style["warm"]["average_score"] == 85.0
    assert by_style["warm"]["best_score"] == 90.0
    assert by_style["warm"]["daily_wins"] == 1
    assert by_style["warm"]["source_wins"] == 1
    assert by_style["warm"]["recent_7_day_average"] == 80.0
    assert by_style["cool"]["recent_7_day_average"] == 100.0
    assert by_style["cool"]["rank"] == 1


def test_read_and_write_style_analytics_uses_compacted_runs(tmp_path):
    logs_dir = tmp_path / "logs"
    docs_data_dir = tmp_path / "docs" / "data"
    append_jsonl(logs_dir / "runs.jsonl", {"run_date": "2026-06-01", "outputs": [output("old", 1, "2026-06-01", "old")]})
    append_jsonl(logs_dir / "runs.jsonl", {"run_date": "2026-06-02", "outputs": [output("new", 99, "2026-06-02", "new")]})

    runs = read_compacted_runs(logs_dir / "runs.jsonl", limit=1)
    analytics = write_style_analytics(logs_dir, docs_data_dir, limit=1)

    assert len(runs) == 1
    assert analytics["styles"][0]["style"] == "new"
    assert (logs_dir / "style_analytics.json").exists()
    assert (docs_data_dir / "style-analytics.json").exists()
