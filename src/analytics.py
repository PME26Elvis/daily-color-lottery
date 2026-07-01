from __future__ import annotations

from collections import defaultdict
from datetime import date, timedelta
from pathlib import Path
from typing import Any

from src.utils import load_jsonl, write_json


def _score_value(output: dict[str, Any]) -> float | None:
    score = output.get("score")
    if isinstance(score, dict):
        score = score.get("score")
    try:
        return float(score)
    except (TypeError, ValueError):
        return None


def _parse_date(value: Any) -> date | None:
    if not isinstance(value, str):
        return None
    try:
        return date.fromisoformat(value[:10])
    except ValueError:
        return None


def iter_run_outputs(runs: list[dict[str, Any]]) -> list[dict[str, Any]]:
    """Flatten output records from compacted run summaries."""
    rows: list[dict[str, Any]] = []
    for run in runs:
        run_date = run.get("run_date")
        run_id = run.get("run_id")
        best_path = None
        best_output = run.get("best_output")
        if isinstance(best_output, dict):
            best_path = best_output.get("output_path")
        for output in run.get("outputs") or []:
            if not isinstance(output, dict):
                continue
            row = dict(output)
            row.setdefault("run_date", run_date)
            row.setdefault("run_id", run_id)
            row["daily_win"] = bool(best_path and row.get("output_path") == best_path)
            rows.append(row)
    return rows


def build_style_analytics(runs: list[dict[str, Any]]) -> dict[str, Any]:
    """Aggregate style performance metrics from compacted run summaries."""
    outputs = iter_run_outputs(runs)
    by_style: dict[str, list[dict[str, Any]]] = defaultdict(list)
    dates = [_parse_date(run.get("run_date")) for run in runs]
    valid_dates = [run_date for run_date in dates if run_date is not None]
    latest_date = max(valid_dates) if valid_dates else None
    recent_start = latest_date - timedelta(days=6) if latest_date else None

    for output in outputs:
        style = output.get("style") or "unknown"
        if _score_value(output) is None:
            continue
        by_style[str(style)].append(output)

    styles = []
    for style, rows in by_style.items():
        scored = [(row, _score_value(row)) for row in rows]
        scores = [score for _row, score in scored if score is not None]
        recent_scores = []
        for row, score in scored:
            run_date = _parse_date(row.get("run_date"))
            if score is not None and recent_start and run_date and recent_start <= run_date <= latest_date:
                recent_scores.append(score)
        best_row, best_score = max(scored, key=lambda item: item[1] if item[1] is not None else -1)
        styles.append(
            {
                "style": style,
                "count": len(scores),
                "average_score": round(sum(scores) / len(scores), 2),
                "best_score": round(float(best_score), 2),
                "daily_wins": sum(1 for row in rows if row.get("daily_win")),
                "source_wins": sum(1 for row in rows if row.get("best_for_source_today")),
                "recent_7_day_average": round(sum(recent_scores) / len(recent_scores), 2)
                if recent_scores
                else None,
                "best_output": best_row,
            }
        )

    styles.sort(
        key=lambda row: (
            float(row["average_score"]),
            float(row["best_score"]),
            int(row["source_wins"]),
            int(row["daily_wins"]),
            str(row["style"]),
        ),
        reverse=True,
    )
    for index, row in enumerate(styles, start=1):
        row["rank"] = index

    return {
        "run_count": len(runs),
        "output_count": sum(row["count"] for row in styles),
        "latest_run_date": latest_date.isoformat() if latest_date else None,
        "recent_window_days": 7,
        "styles": styles,
    }


def read_compacted_runs(path: Path, limit: int = 365) -> list[dict[str, Any]]:
    return load_jsonl(path)[-limit:]


def write_style_analytics(logs_dir: Path, docs_data_dir: Path, limit: int = 365) -> dict[str, Any]:
    analytics = build_style_analytics(read_compacted_runs(logs_dir / "runs.jsonl", limit=limit))
    write_json(logs_dir / "style_analytics.json", analytics)
    write_json(docs_data_dir / "style-analytics.json", analytics)
    return analytics
