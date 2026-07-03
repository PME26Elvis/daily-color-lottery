
from src.analytics import build_algorithm_analytics, build_source_analytics, build_style_analytics, read_compacted_runs, write_style_analytics
from src.utils import append_jsonl


def output(style, score, run_date, path, source_win=False, source_path="sources/a.png", source_sha256="sha-a", source_name="a.png"):
    return {
        "style": style,
        "run_date": run_date,
        "output_path": path,
        "score": {"score": score},
        "best_for_source_today": source_win,
        "source_path": source_path,
        "source_sha256": source_sha256,
        "source_name": source_name,
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
    assert (logs_dir / "source_analytics.json").exists()
    assert (docs_data_dir / "source-analytics.json").exists()
    assert (docs_data_dir / "algorithm-analytics.json").exists()


def test_build_source_analytics_groups_by_path_and_scores_wins():
    runs = [
        {
            "run_id": "run-1",
            "run_date": "2026-06-20",
            "best_output": {"output_path": "a-warm"},
            "outputs": [
                output("warm", 90, "2026-06-20", "a-warm", source_win=True, source_path="sources/a.png", source_name="a.png"),
                output("cool", 70, "2026-06-20", "a-cool", source_path="sources/a.png", source_name="a.png"),
                output("warm", 95, "2026-06-20", "b-warm", source_win=True, source_path="sources/b.png", source_name="b.png"),
            ],
        },
        {
            "run_id": "run-2",
            "run_date": "2026-06-21",
            "best_output": {"output_path": "b-cool"},
            "outputs": [
                output("cool", 100, "2026-06-21", "b-cool", source_win=True, source_path="sources/b.png", source_name="b.png"),
                output("warm", 50, "2026-06-21", "a-warm-2", source_win=True, source_path="sources/a.png", source_name="a.png"),
                {"style": "ignored", "score": None, "source_path": "sources/a.png", "output_path": "ignored"},
            ],
        },
    ]

    analytics = build_source_analytics(runs)

    by_source = {row["source_key"]: row for row in analytics["sources"]}
    assert analytics["run_count"] == 2
    assert analytics["output_count"] == 5
    assert analytics["latest_run_date"] == "2026-06-21"
    assert by_source["sources/a.png"]["count"] == 3
    assert by_source["sources/a.png"]["average_score"] == 70.0
    assert by_source["sources/a.png"]["best_score"] == 90.0
    assert by_source["sources/a.png"]["daily_wins"] == 1
    assert by_source["sources/a.png"]["source_wins"] == 2
    assert by_source["sources/a.png"]["best_style"] == "warm"
    assert by_source["sources/b.png"]["rank"] == 1


def test_build_source_analytics_falls_back_to_sha_for_missing_path():
    runs = [
        {
            "run_date": "2026-06-20",
            "best_output": {"output_path": "sha-output"},
            "outputs": [
                output("warm", 88, "2026-06-20", "sha-output", source_path=None, source_sha256="abc123", source_name=None),
            ],
        }
    ]

    analytics = build_source_analytics(runs)

    assert analytics["sources"][0]["source_key"] == "abc123"
    assert analytics["sources"][0]["source_sha256"] == "abc123"
    assert analytics["sources"][0]["daily_wins"] == 1


def test_build_algorithm_analytics_groups_algorithms_and_profile_buckets():
    runs = [{"run_id":"r1","run_date":"2026-06-30","best_output":{"output_path":"a1"},"outputs":[
        {**output("warm", 90, "2026-06-30", "a1", source_win=True), "algorithm":"adaptive_auto_enhance", "source_profile_bucket":"low-light"},
        {**output("cool", 80, "2026-06-30", "a2"), "algorithm":"palette_cinematic", "source_profile":{"profile_bucket":"colorful"}},
    ]}]
    analytics = build_algorithm_analytics(runs)
    by_alg = {row["algorithm"]: row for row in analytics["algorithms"]}
    by_bucket = {row["profile_bucket"]: row for row in analytics["profile_buckets"]}
    assert by_alg["adaptive_auto_enhance"]["average_score"] == 90.0
    assert by_alg["adaptive_auto_enhance"]["usage_count"] == 1
    assert by_bucket["low-light"]["count"] == 1
    assert by_bucket["colorful"]["best_score"] == 80.0
