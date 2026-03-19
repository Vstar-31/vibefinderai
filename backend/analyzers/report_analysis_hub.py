#!/usr/bin/env python3
"""
Unified report analyzer for VibeFinderAI.

This module consolidates legacy report analyzers into one CLI program.
It can read the latest batch JSON report, CSV report, and Gemini log, then
write consolidated outputs under analysis_reports/.
"""

from __future__ import annotations

import argparse
import csv
import json
import re
from collections import Counter, defaultdict
from dataclasses import dataclass
from datetime import datetime
from pathlib import Path
from typing import Any, Dict, List, Optional


@dataclass
class UnifiedRow:
    prompt_num: int
    input_text: str
    vibe: str
    track_count: int
    language: str = "Any"
    relevancy: Optional[float] = None
    accuracy: Optional[float] = None
    latency_ms: Optional[float] = None
    gemini_verdict: Optional[str] = None


def _latest_file(folder: Path, pattern: str) -> Optional[Path]:
    files = sorted(folder.glob(pattern), key=lambda p: p.stat().st_mtime, reverse=True)
    return files[0] if files else None


def _candidate_report_dirs() -> List[Path]:
    script_dir = Path(__file__).resolve().parent
    backend_dir = script_dir.parent
    candidates = [
        Path.cwd() / "analysis_reports",
        backend_dir / "analysis_reports",
        backend_dir.parent / "analysis_reports",
    ]

    seen = set()
    out: List[Path] = []
    for p in candidates:
        rp = p.resolve()
        if rp not in seen:
            out.append(p)
            seen.add(rp)
    return out


def _latest_file_from_dirs(pattern: str) -> Optional[Path]:
    matches: List[Path] = []
    for d in _candidate_report_dirs():
        if d.exists():
            matches.extend(d.glob(pattern))
    if not matches:
        return None
    return sorted(matches, key=lambda p: p.stat().st_mtime, reverse=True)[0]


def _default_output_dir() -> Path:
    for d in _candidate_report_dirs():
        if d.exists():
            return d
    # Fall back to backend/analysis_reports when nothing exists yet.
    return _candidate_report_dirs()[1]


def _load_batch_json(json_path: Path) -> tuple[list[UnifiedRow], Dict[str, Any]]:
    """
    Load rows from a batch_analysis_*.json report.

    BUG FIXED: The original code read from `recent_samples`, which is capped at 200 entries.
    Even a fully successful 20k-prompt run would only show 200 rows here.

    Fix: read from the `detail_file` JSONL path embedded in summary.detail_file first.
    If that file exists, stream all rows from it. Fall back to recent_samples only if
    the detail file is missing (e.g. running against an old report with no JSONL).

    BUG FIXED #2: field was `sample.get("vibe")` but actual path is
    `sample["engine_output"]["dominant_vibe"]`.
    """
    with json_path.open("r", encoding="utf-8", errors="ignore") as f:
        data = json.load(f)

    # Prefer the full detail JSONL over the 200-row recent_samples cap
    detail_file_str = data.get("summary", {}).get("detail_file", "")
    detail_path: Optional[Path] = None

    if detail_file_str:
        candidate = Path(detail_file_str)
        if not candidate.is_absolute():
            candidate = json_path.parent / candidate
        if candidate.exists():
            detail_path = candidate

    if detail_path:
        rows = _load_prompt_level_jsonl(detail_path)
        return rows, data

    # Fallback: recent_samples (200-row cap — only used when no JSONL available)
    rows: List[UnifiedRow] = []
    for idx, sample in enumerate(data.get("recent_samples", []), 1):
        engine_out = sample.get("engine_output", {}) or {}
        rows.append(
            UnifiedRow(
                prompt_num=sample.get("prompt_index", idx),
                input_text=sample.get("prompt", ""),
                vibe=engine_out.get("dominant_vibe", "unknown") or "unknown",
                track_count=int(engine_out.get("track_count", 0) or 0),
                language=sample.get("language", "Any"),
                latency_ms=float(sample.get("latency_ms", 0.0) or 0.0),
            )
        )

    return rows, data


def _load_prompt_level_jsonl(jsonl_path: Path) -> List["UnifiedRow"]:
    """
    Stream-load all rows from a prompt_level_results_*.jsonl file.

    This is the canonical source of truth for a batch run — it contains every
    prompt, not just the 200 recent_samples kept in the summary JSON.

    For very large files (20k × ~2KB = ~40MB) we stream line-by-line to avoid
    loading the whole file into memory at once.
    """
    rows: List[UnifiedRow] = []
    with jsonl_path.open("r", encoding="utf-8", errors="ignore") as f:
        for idx, line in enumerate(f, 1):
            line = line.strip()
            if not line:
                continue
            try:
                raw = json.loads(line)
            except json.JSONDecodeError:
                continue

            req = raw.get("request_payload", {}) or {}
            out = raw.get("engine_output", {}) or {}
            rel = raw.get("relevance", {}) or {}

            track_count = out.get("track_count")
            if track_count is None:
                track_count = len(out.get("tracks", []) or [])

            score = rel.get("relevancy_score")
            try:
                relevancy = float(score) if score is not None else None
            except (TypeError, ValueError):
                relevancy = None

            latency_raw = raw.get("latency_ms")
            try:
                latency = float(latency_raw) if latency_raw is not None else None
            except (TypeError, ValueError):
                latency = None

            # gemini_verdict is in relevance.verdict for batch runs (heuristic or inline)
            # and in gemini_relevance.verdict for post-graded JSONL
            gem_rel = raw.get("gemini_relevance") or rel
            verdict_raw = gem_rel.get("verdict", "")
            gemini_verdict = (verdict_raw or "").upper() or None
            if gemini_verdict not in {"PASS", "PARTIAL", "FAIL"}:
                gemini_verdict = None

            rows.append(
                UnifiedRow(
                    prompt_num=int(raw.get("prompt_index", idx) or idx),
                    input_text=raw.get("prompt") or req.get("text", ""),
                    vibe=out.get("dominant_vibe", "unknown") or "unknown",
                    track_count=int(track_count or 0),
                    language=req.get("language", raw.get("language", "Any")) or "Any",
                    relevancy=relevancy,
                    accuracy=None,
                    latency_ms=latency,
                    gemini_verdict=gemini_verdict,
                )
            )
    return rows


def _load_gemini_graded_jsonl(jsonl_path: Path) -> List[UnifiedRow]:
    rows: List[UnifiedRow] = []
    with jsonl_path.open("r", encoding="utf-8", errors="ignore") as f:
        for idx, line in enumerate(f, 1):
            line = line.strip()
            if not line:
                continue
            try:
                raw = json.loads(line)
            except json.JSONDecodeError:
                continue

            req = raw.get("request_payload", {})
            out = raw.get("engine_output", {})
            gem = raw.get("gemini_relevance", raw.get("relevance", {}))

            track_count = out.get("track_count")
            if track_count is None:
                tracks = out.get("tracks", []) or []
                track_count = len(tracks)

            score = gem.get("relevancy_score")
            try:
                relevancy = float(score) if score is not None else None
            except (TypeError, ValueError):
                relevancy = None

            latency_raw = raw.get("latency_ms")
            try:
                latency = float(latency_raw) if latency_raw is not None else None
            except (TypeError, ValueError):
                latency = None

            rows.append(
                UnifiedRow(
                    prompt_num=int(raw.get("prompt_index", idx) or idx),
                    input_text=raw.get("prompt") or req.get("text", ""),
                    vibe=out.get("dominant_vibe", "unknown") or "unknown",
                    track_count=int(track_count or 0),
                    language=req.get("language", raw.get("language", "Any")) or "Any",
                    relevancy=relevancy,
                    accuracy=None,
                    latency_ms=latency,
                    gemini_verdict=(gem.get("verdict") or "").upper() or None,
                )
            )
    return rows


def _load_data_csv(csv_path: Path) -> List[UnifiedRow]:
    rows: List[UnifiedRow] = []
    with csv_path.open("r", encoding="utf-8", errors="ignore") as f:
        reader = csv.DictReader(f)
        for raw in reader:
            rows.append(
                UnifiedRow(
                    prompt_num=int(raw.get("PromptNum", 0) or 0),
                    input_text=(raw.get("Input", "") or "").strip('"'),
                    vibe=raw.get("Vibe", "unknown") or "unknown",
                    track_count=int(raw.get("TrackCount", 0) or 0),
                    language=raw.get("Language", "Any") or "Any",
                    relevancy=float(raw.get("Relevancy", 0) or 0),
                    accuracy=float(raw.get("Accuracy", 0) or 0),
                )
            )
    return rows


def _parse_gemini_log(log_path: Optional[Path]) -> Dict[str, int]:
    if not log_path or not log_path.exists():
        return {"hit": 0, "partial": 0, "miss": 0}

    text = log_path.read_text(encoding="utf-8", errors="ignore").lower()
    return {
        "hit": len(re.findall(r"\bhit\b", text)),
        "partial": len(re.findall(r"\bpartial\b", text)),
        "miss": len(re.findall(r"\bmiss\b", text)),
    }


def _avg(nums: List[float]) -> float:
    return (sum(nums) / len(nums)) if nums else 0.0


def _build_stats(rows: List[UnifiedRow]) -> Dict[str, Any]:
    vibe_groups: Dict[str, List[UnifiedRow]] = defaultdict(list)
    for row in rows:
        vibe_groups[row.vibe].append(row)

    vibe_breakdown = []
    for vibe, group in sorted(vibe_groups.items(), key=lambda kv: len(kv[1]), reverse=True):
        rel_vals = [r.relevancy for r in group if r.relevancy is not None]
        acc_vals = [r.accuracy for r in group if r.accuracy is not None]
        lat_vals = [r.latency_ms for r in group if r.latency_ms is not None]

        vibe_breakdown.append(
            {
                "vibe": vibe,
                "count": len(group),
                "avg_track_count": round(_avg([float(r.track_count) for r in group]), 2),
                "avg_relevancy": round(_avg(rel_vals), 2) if rel_vals else None,
                "avg_accuracy": round(_avg(acc_vals), 2) if acc_vals else None,
                "avg_latency_ms": round(_avg(lat_vals), 3) if lat_vals else None,
            }
        )

    problems = []
    for r in rows:
        if r.relevancy is not None:
            if r.relevancy < 50:
                problems.append(r)
        else:
            if r.track_count == 0:
                problems.append(r)

    language_counts = Counter(r.language for r in rows)
    rel_all = [r.relevancy for r in rows if r.relevancy is not None]
    acc_all = [r.accuracy for r in rows if r.accuracy is not None]
    lat_all = [r.latency_ms for r in rows if r.latency_ms is not None]
    gemini_counts = Counter(
        r.gemini_verdict for r in rows if r.gemini_verdict in {"PASS", "PARTIAL", "FAIL"}
    )

    return {
        "total_rows": len(rows),
        "avg_relevancy": round(_avg(rel_all), 2) if rel_all else None,
        "avg_accuracy": round(_avg(acc_all), 2) if acc_all else None,
        "avg_latency_ms": round(_avg(lat_all), 3) if lat_all else None,
        "gemini_verdict_counts": {
            "PASS": gemini_counts.get("PASS", 0),
            "PARTIAL": gemini_counts.get("PARTIAL", 0),
            "FAIL": gemini_counts.get("FAIL", 0),
        },
        "vibe_breakdown": vibe_breakdown,
        "language_counts": dict(language_counts),
        "problem_rows": problems,
    }


def _write_outputs(
    out_dir: Path,
    stats: Dict[str, Any],
    gemini_stats: Dict[str, int],
    source_info: Dict[str, Optional[str]],
) -> Dict[str, Path]:
    out_dir.mkdir(parents=True, exist_ok=True)
    ts = datetime.now().strftime("%Y%m%d_%H%M%S")

    consolidated_json = out_dir / f"CONSOLIDATED_ANALYSIS_{ts}.json"
    master_txt = out_dir / "ANALYSIS_MASTER_REPORT.txt"
    index_txt = out_dir / "INDEX_ANALYSIS.txt"
    vibe_txt = out_dir / "VIBE_ANALYSIS_DETAILED.txt"
    problem_txt = out_dir / "PROBLEM_PROMPTS_ANALYSIS.txt"

    payload = {
        "generated_at": datetime.now().isoformat(),
        "sources": source_info,
        "stats": {
            k: v for k, v in stats.items() if k != "problem_rows"
        },
        "gemini": gemini_stats,
        "problem_rows": [
            {
                "prompt_num": r.prompt_num,
                "input": r.input_text,
                "vibe": r.vibe,
                "track_count": r.track_count,
                "relevancy": r.relevancy,
                "accuracy": r.accuracy,
                "language": r.language,
            }
            for r in stats["problem_rows"]
        ],
    }
    consolidated_json.write_text(json.dumps(payload, indent=2), encoding="utf-8")

    master_lines = [
        "VIBEFINDER AI - CONSOLIDATED ANALYSIS MASTER REPORT",
        "=" * 80,
        f"Generated: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}",
        f"Total prompts analyzed: {stats['total_rows']}",
        f"Average relevancy: {stats['avg_relevancy'] if stats['avg_relevancy'] is not None else 'N/A'}",
        f"Average accuracy: {stats['avg_accuracy'] if stats['avg_accuracy'] is not None else 'N/A'}",
        f"Average latency (ms): {stats['avg_latency_ms'] if stats['avg_latency_ms'] is not None else 'N/A'}",
        f"Gemini hits/partials/misses: {gemini_stats['hit']}/{gemini_stats['partial']}/{gemini_stats['miss']}",
        (
            "Gemini PASS/PARTIAL/FAIL (from graded JSONL): "
            f"{stats['gemini_verdict_counts']['PASS']}/"
            f"{stats['gemini_verdict_counts']['PARTIAL']}/"
            f"{stats['gemini_verdict_counts']['FAIL']}"
        ),
        "",
        "Top vibes:",
    ]
    for row in stats["vibe_breakdown"][:10]:
        master_lines.append(f"- {row['vibe']}: {row['count']} prompts")
    master_lines.append("")
    master_lines.append(f"Problem prompts: {len(stats['problem_rows'])}")
    master_txt.write_text("\n".join(master_lines), encoding="utf-8")

    index_lines = [
        "ANALYSIS INDEX",
        "=" * 80,
        f"- {consolidated_json.name}",
        f"- {master_txt.name}",
        f"- {index_txt.name}",
        f"- {vibe_txt.name}",
        f"- {problem_txt.name}",
    ]
    index_txt.write_text("\n".join(index_lines), encoding="utf-8")

    vibe_lines = ["DETAILED VIBE ANALYSIS", "=" * 80]
    for row in stats["vibe_breakdown"]:
        vibe_lines.append(
            f"{row['vibe']}: count={row['count']}, avg_track_count={row['avg_track_count']}, "
            f"avg_relevancy={row['avg_relevancy']}, avg_accuracy={row['avg_accuracy']}, "
            f"avg_latency_ms={row['avg_latency_ms']}"
        )
    vibe_txt.write_text("\n".join(vibe_lines), encoding="utf-8")

    problem_lines = ["PROBLEM PROMPTS", "=" * 80]
    for r in stats["problem_rows"][:200]:
        problem_lines.append(
            f"#{r.prompt_num} [{r.vibe}] tracks={r.track_count} rel={r.relevancy} acc={r.accuracy} :: {r.input_text}"
        )
    if len(stats["problem_rows"]) > 200:
        problem_lines.append(f"... truncated, total problems: {len(stats['problem_rows'])}")
    problem_txt.write_text("\n".join(problem_lines), encoding="utf-8")

    return {
        "consolidated_json": consolidated_json,
        "master_txt": master_txt,
        "index_txt": index_txt,
        "vibe_txt": vibe_txt,
        "problem_txt": problem_txt,
    }


def run(
    output_dir: Path,
    batch_json: Optional[Path],
    data_csv: Optional[Path],
    gemini_log: Optional[Path],
    gemini_graded_jsonl: Optional[Path],
) -> Dict[str, Path]:
    rows: List[UnifiedRow] = []
    source_info: Dict[str, Optional[str]] = {
        "batch_json": str(batch_json) if batch_json else None,
        "data_csv": str(data_csv) if data_csv else None,
        "gemini_log": str(gemini_log) if gemini_log else None,
        "gemini_graded_jsonl": str(gemini_graded_jsonl) if gemini_graded_jsonl else None,
    }

    # Priority 1: post-Gemini-graded JSONL (most authoritative)
    if gemini_graded_jsonl and gemini_graded_jsonl.exists():
        rows = _load_gemini_graded_jsonl(gemini_graded_jsonl)

    # Priority 2: batch_analysis JSON — but read its embedded detail JSONL for full row count
    elif batch_json and batch_json.exists():
        rows, _ = _load_batch_json(batch_json)

    # Priority 3: raw prompt_level_results JSONL (all rows, no Gemini scores)
    elif not rows:
        prompt_jsonl = _latest_file_from_dirs("prompt_level_results_*.jsonl")
        if prompt_jsonl and prompt_jsonl.exists():
            rows = _load_prompt_level_jsonl(prompt_jsonl)
            source_info["prompt_level_jsonl"] = str(prompt_jsonl)

    # Priority 4: legacy CSV
    elif data_csv and data_csv.exists():
        rows = _load_data_csv(data_csv)

    if not rows:
        raise RuntimeError("No analysis data found. Provide a valid DATA_*.csv, batch_analysis_*.json, or prompt_level_results_*.jsonl")

    gemini_stats = _parse_gemini_log(gemini_log)
    stats = _build_stats(rows)
    return _write_outputs(output_dir, stats, gemini_stats, source_info)


def _build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description="Unified report analyzer for VibeFinderAI")
    parser.add_argument("--output-dir", default="analysis_reports", help="Output directory")
    parser.add_argument("--batch-json", default=None, help="Path to batch_analysis_*.json")
    parser.add_argument("--data-csv", default=None, help="Path to DATA_*.csv")
    parser.add_argument("--gemini-log", default=None, help="Path to Gemini log")
    parser.add_argument("--gemini-graded-jsonl", default=None, help="Path to gemini_graded_*.jsonl")
    return parser


def main(argv: Optional[List[str]] = None) -> int:
    args = _build_parser().parse_args(argv)

    root = Path.cwd()

    batch_json = Path(args.batch_json) if args.batch_json else _latest_file_from_dirs("batch_analysis_*.json")
    data_csv = Path(args.data_csv) if args.data_csv else _latest_file_from_dirs("DATA_*.csv")
    gemini_graded_jsonl = (
        Path(args.gemini_graded_jsonl)
        if args.gemini_graded_jsonl
        else _latest_file_from_dirs("gemini_graded_*.jsonl")
    )

    if args.output_dir != "analysis_reports":
        out_dir = Path(args.output_dir)
        if not out_dir.is_absolute():
            out_dir = root / out_dir
    else:
        detected_source = gemini_graded_jsonl or data_csv or batch_json
        if detected_source is None:
            # Also check for prompt_level_results directly
            detected_source = _latest_file_from_dirs("prompt_level_results_*.jsonl")
        out_dir = detected_source.parent if detected_source else _default_output_dir()

    if args.gemini_log:
        gemini_log = Path(args.gemini_log)
    else:
        script_dir = Path(__file__).resolve().parent
        backend_dir = script_dir.parent
        gemini_log = (
            _latest_file(root, "qa_batch_gemini_*.log")
            or _latest_file(backend_dir, "qa_batch_gemini_*.log")
        )
    if gemini_log is None:
        script_dir = Path(__file__).resolve().parent
        backend_dir = script_dir.parent
        gemini_log = (
            _latest_file(root, "qa_batch_gemini_analysis*.log")
            or _latest_file(backend_dir, "qa_batch_gemini_analysis*.log")
        )

    outputs = run(out_dir, batch_json, data_csv, gemini_log, gemini_graded_jsonl)
    print("Consolidated analysis generated:")
    for key, value in outputs.items():
        print(f"  {key}: {value}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
