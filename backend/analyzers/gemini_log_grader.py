#!/usr/bin/env python3
"""
Post-process Vibefinder batch JSONL logs with Gemini relevance grading.

Usage examples:
    python analyzers/gemini_log_grader.py
    python analyzers/gemini_log_grader.py --input analysis_reports/prompt_level_results_20260319_123000.jsonl
    python analyzers/gemini_log_grader.py --limit 500 --concurrency 3

Input JSONL format:
- One object per line from batch_tester_v10k_2.py detail output.

Outputs:
- analysis_reports/gemini_graded_<timestamp>.jsonl  (streamed — safe to interrupt)
- analysis_reports/gemini_graded_summary_<timestamp>.json

RESUME SUPPORT:
    If a graded output already exists for the same input file, pass it via --resume
    and only ungraded rows will be processed:
        python analyzers/gemini_log_grader.py --resume analysis_reports/gemini_graded_XYZ.jsonl
"""

import argparse
import asyncio
import json
import os
import logging
from datetime import datetime
from pathlib import Path
from typing import Any, Dict, List, Optional, Set, Tuple

from dotenv import load_dotenv

try:
    import aiohttp
except ImportError as exc:
    raise RuntimeError("aiohttp is required for gemini_log_grader.py") from exc


# Always load from backend/.env (script lives in backend/analyzers/ → parent.parent)
_script_env = Path(__file__).resolve().parent.parent / ".env"
load_dotenv(dotenv_path=_script_env, override=False)
load_dotenv(override=False)  # CWD fallback

GEMINI_API_KEY = os.getenv("GEMINI_API_KEY")
if not GEMINI_API_KEY:
    raise RuntimeError("GEMINI_API_KEY is missing in environment")

GEMINI_MODEL = os.getenv("GEMINI_MODEL", "gemini-2.5-flash")
GEMINI_URL = (
    f"https://generativelanguage.googleapis.com/v1beta/models/{GEMINI_MODEL}:generateContent"
    f"?key={GEMINI_API_KEY}"
)

# Per-task timeout — one slow Gemini call used to block a semaphore slot forever.
# At concurrency=2 this meant the last N prompts never started.
PER_TASK_TIMEOUT_SECONDS: int = 90


def _build_logger(log_file: Path) -> logging.Logger:
    # Use a unique logger name per invocation to avoid handler accumulation
    # when the module is imported multiple times (e.g. in tests).
    logger = logging.getLogger(f"gemini_log_grader.{id(log_file)}")
    logger.setLevel(logging.INFO)
    logger.handlers = []

    log_file.parent.mkdir(parents=True, exist_ok=True)
    fmt = logging.Formatter("[%(asctime)s] %(levelname)s: %(message)s", datefmt="%H:%M:%S")

    fh = logging.FileHandler(log_file, encoding="utf-8")
    fh.setFormatter(fmt)
    sh = logging.StreamHandler()
    sh.setFormatter(fmt)

    logger.addHandler(fh)
    logger.addHandler(sh)
    return logger


def _candidate_report_dirs() -> List[Path]:
    """Return report directories in priority order for any current working directory."""
    script_dir = Path(__file__).resolve().parent
    backend_dir = script_dir.parent

    candidates = [
        Path.cwd() / "analysis_reports",
        backend_dir / "analysis_reports",
        backend_dir.parent / "analysis_reports",
    ]

    seen: set = set()
    unique_candidates: List[Path] = []
    for p in candidates:
        rp = p.resolve()
        if rp not in seen:
            unique_candidates.append(p)
            seen.add(rp)
    return unique_candidates


def _find_latest_input() -> Path:
    all_matches: List[Path] = []
    for report_dir in _candidate_report_dirs():
        if not report_dir.exists():
            continue
        all_matches.extend(report_dir.glob("prompt_level_results_*.jsonl"))

    candidates = sorted(all_matches, key=lambda p: p.stat().st_mtime, reverse=True)
    if not candidates:
        tried = ", ".join(str(p) for p in _candidate_report_dirs())
        raise FileNotFoundError(
            f"No prompt_level_results_*.jsonl found. Checked: {tried}"
        )
    return candidates[0]


def _load_jsonl(path: Path, limit: int) -> List[Dict[str, Any]]:
    rows: List[Dict[str, Any]] = []
    with path.open("r", encoding="utf-8") as f:
        for line in f:
            line = line.strip()
            if not line:
                continue
            try:
                rows.append(json.loads(line))
            except json.JSONDecodeError:
                continue
            if limit > 0 and len(rows) >= limit:
                break
    return rows


def _load_already_graded(resume_path: Optional[Path]) -> Set[int]:
    """
    Returns a set of prompt_index values already present in a partial output file.
    Used to skip rows that succeeded in a previous interrupted run.
    """
    if not resume_path or not resume_path.exists():
        return set()
    done: Set[int] = set()
    with resume_path.open("r", encoding="utf-8") as f:
        for line in f:
            line = line.strip()
            if not line:
                continue
            try:
                obj = json.loads(line)
                idx = obj.get("prompt_index") or obj.get("gemini_graded_index")
                if idx is not None:
                    done.add(int(idx))
            except (json.JSONDecodeError, ValueError):
                continue
    return done


def _tracks_preview(tracks: List[Dict[str, Any]], max_items: int = 12) -> str:
    items = []
    for t in tracks[:max_items]:
        title = t.get("title") or ""
        artist = t.get("artist") or ""
        items.append(f"{title} by {artist}".strip())
    return ", ".join(items) if items else "NO_TRACKS"


def _build_gemini_prompt(row: Dict[str, Any]) -> Tuple[str, str]:
    req = row.get("request_payload", {})
    out = row.get("engine_output", {})
    tracks = out.get("tracks") or []

    system_prompt = (
        "You are an expert music recommendation evaluator. "
        "Judge alignment between user intent and returned tracks, considering language, locks, and knobs."
    )

    user_prompt = f"""
Prompt text: {req.get('text', row.get('prompt', ''))}
Language: {req.get('language', row.get('language', 'Any'))}
Knobs: artist_focus={req.get('artist_focus')}, bpm_focus={req.get('bpm_focus')}, nicheness={req.get('nicheness')}, track_limit={req.get('track_limit')}
Artist lock: {req.get('override_artist')}
Genre lock: {req.get('override_genre')}
Secondary vibe mode: {req.get('use_secondary_vibe', False)}
Dismiss detected artist: {req.get('dismiss_detected_artist', False)}

Engine output:
- dominant_vibe: {out.get('dominant_vibe')}
- confidence: {out.get('confidence')}
- secondary_vibe: {out.get('secondary_vibe')}
- secondary_confidence: {out.get('secondary_confidence')}
- genres: {out.get('genres', [])}
- matched_keywords: {out.get('matched_keywords', [])}
- detected_artist: {out.get('detected_artist')}
- track_count: {out.get('track_count', 0)}
- tracks: {_tracks_preview(tracks)}

Return ONLY strict JSON with this schema:
{{
  "verdict": "PASS" | "PARTIAL" | "FAIL",
  "relevancy_score": 0-100,
  "reason": "short reason",
  "issues": ["issue"],
  "improvements": ["improvement"]
}}
""".strip()

    return system_prompt, user_prompt


async def _call_gemini(
    session: aiohttp.ClientSession,
    row: Dict[str, Any],
    retries: int = 4,
) -> Dict[str, Any]:
    system_prompt, user_prompt = _build_gemini_prompt(row)
    payload = {
        "contents": [{"parts": [{"text": user_prompt}]}],
        "systemInstruction": {"parts": [{"text": system_prompt}]},
        "generationConfig": {"responseMimeType": "application/json"},
    }

    wait_seconds = 2
    for attempt in range(retries):
        try:
            async with session.post(
                GEMINI_URL, json=payload,
                timeout=aiohttp.ClientTimeout(total=60),
            ) as resp:
                if resp.status == 200:
                    data = await resp.json()
                    text_resp = (
                        data.get("candidates", [{}])[0]
                        .get("content", {})
                        .get("parts", [{}])[0]
                        .get("text", "")
                    )
                    parsed = json.loads(text_resp)
                    verdict = str(parsed.get("verdict", "FAIL")).upper()
                    if verdict not in {"PASS", "PARTIAL", "FAIL"}:
                        verdict = "FAIL"
                    score = parsed.get("relevancy_score", 0)
                    if not isinstance(score, (int, float)):
                        score = 0
                    return {
                        "verdict": verdict,
                        "relevancy_score": max(0, min(100, int(score))),
                        "reason": parsed.get("reason", ""),
                        "issues": parsed.get("issues", []),
                        "improvements": parsed.get("improvements", []),
                    }

                if resp.status == 429:
                    await asyncio.sleep(wait_seconds)
                    wait_seconds *= 2
                    continue

                body = await resp.text()
                return {
                    "verdict": "FAIL",
                    "relevancy_score": 0,
                    "reason": f"http_{resp.status}",
                    "issues": [body[:200]],
                    "improvements": ["retry_postprocess"],
                }
        except Exception as exc:
            if attempt == retries - 1:
                return {
                    "verdict": "FAIL",
                    "relevancy_score": 0,
                    "reason": f"exception_{type(exc).__name__}",
                    "issues": [str(exc)[:200]],
                    "improvements": ["check_quota_and_key"],
                }
            await asyncio.sleep(wait_seconds)
            wait_seconds *= 2

    return {
        "verdict": "FAIL",
        "relevancy_score": 0,
        "reason": "unknown",
        "issues": ["unexpected_fallback"],
        "improvements": ["rerun_grader"],
    }


async def _grade_rows(
    rows: List[Dict[str, Any]],
    concurrency: int,
    output_path: Path,
    logger: logging.Logger,
    already_graded: Set[int],
) -> List[Dict[str, Any]]:
    """
    Grade rows with per-task timeout.

    Key fix: wrap each _call_gemini in asyncio.wait_for(timeout=PER_TASK_TIMEOUT_SECONDS).
    Previously, one hung Gemini call blocked a semaphore slot forever. With concurrency=2,
    that meant the last N prompts never started. Now each task has a hard ceiling.

    Results are streamed to output_path as they complete — safe to Ctrl+C and resume.
    """
    sem = asyncio.Semaphore(concurrency)
    connector = aiohttp.TCPConnector(limit=max(16, concurrency * 3))
    # per-call timeout managed via asyncio.wait_for, not the session timeout
    timeout = aiohttp.ClientTimeout(total=None)
    total = len(rows)
    done_count = 0
    timed_out_count = 0
    results: List[Dict[str, Any]] = []

    output_path.parent.mkdir(parents=True, exist_ok=True)
    out_file = output_path.open("a", encoding="utf-8")  # append — supports resume

    try:
        async with aiohttp.ClientSession(connector=connector, timeout=timeout) as session:

            async def run_one(idx: int, row: Dict[str, Any]) -> Optional[Dict[str, Any]]:
                prompt_idx = row.get("prompt_index", idx)
                if prompt_idx in already_graded:
                    return None

                async with sem:
                    try:
                        grade = await asyncio.wait_for(
                            _call_gemini(session, row),
                            timeout=PER_TASK_TIMEOUT_SECONDS,
                        )
                    except asyncio.TimeoutError:
                        nonlocal timed_out_count
                        timed_out_count += 1
                        logger.warning(
                            f"[TIMEOUT] Row {prompt_idx} timed out after {PER_TASK_TIMEOUT_SECONDS}s — marking FAIL"
                        )
                        grade = {
                            "verdict": "FAIL",
                            "relevancy_score": 0,
                            "reason": f"grader_timeout_{PER_TASK_TIMEOUT_SECONDS}s",
                            "issues": ["grader_timed_out"],
                            "improvements": ["rerun_grader_for_this_row"],
                        }

                    output = dict(row)
                    output["gemini_relevance"] = grade
                    output["gemini_graded_at"] = datetime.now().isoformat()
                    output["gemini_graded_index"] = idx

                    out_file.write(json.dumps(output, ensure_ascii=False) + "\n")
                    out_file.flush()

                    return output

            tasks = [asyncio.create_task(run_one(i + 1, row)) for i, row in enumerate(rows)]
            pending = set(tasks)

            while pending:
                done, pending = await asyncio.wait(pending, timeout=10, return_when=asyncio.FIRST_COMPLETED)

                if not done:
                    logger.info(
                        f"[HEARTBEAT] Gemini grading in progress | completed={done_count}/{total} | pending={len(pending)}"
                    )
                    continue

                for task in done:
                    result = await task
                    if result is not None:
                        results.append(result)
                    done_count += 1
                    if done_count % 50 == 0 or done_count == total:
                        logger.info(f"[PROGRESS] Graded {done_count}/{total} rows ({(done_count/total)*100:.1f}%)")

    finally:
        out_file.close()

    if timed_out_count:
        logger.warning(f"[SUMMARY] {timed_out_count}/{total} rows timed out and were marked FAIL.")

    return results


def _summarize(rows: List[Dict[str, Any]]) -> Dict[str, Any]:
    verdicts: Dict[str, int] = {"PASS": 0, "PARTIAL": 0, "FAIL": 0}
    scores: List[int] = []
    primary_confidences: List[float] = []
    secondary_confidences: List[float] = []

    for row in rows:
        rel = row.get("gemini_relevance", {})
        v = str(rel.get("verdict", "FAIL")).upper()
        if v not in verdicts:
            v = "FAIL"
        verdicts[v] += 1

        s = rel.get("relevancy_score", 0)
        if isinstance(s, (int, float)):
            scores.append(int(s))

        out = row.get("engine_output", {})
        pc = out.get("confidence")
        if isinstance(pc, (int, float)):
            primary_confidences.append(float(pc))
        sc = out.get("secondary_confidence")
        if isinstance(sc, (int, float)):
            secondary_confidences.append(float(sc))

    avg_score = (sum(scores) / len(scores)) if scores else 0
    avg_primary_conf = (sum(primary_confidences) / len(primary_confidences)) if primary_confidences else 0
    avg_secondary_conf = (sum(secondary_confidences) / len(secondary_confidences)) if secondary_confidences else 0

    return {
        "total_graded": len(rows),
        "gemini_model": GEMINI_MODEL,
        "verdicts": verdicts,
        "avg_relevancy_score": round(avg_score, 2),
        "avg_primary_confidence": round(avg_primary_conf, 4),
        "avg_secondary_confidence": round(avg_secondary_conf, 4),
        "timestamp": datetime.now().isoformat(),
    }


def _write_json(path: Path, payload: Dict[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", encoding="utf-8") as f:
        json.dump(payload, f, indent=2, ensure_ascii=False)


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Grade Vibefinder batch JSONL logs with Gemini")
    parser.add_argument("--input", type=str, default="", help="Input JSONL file path")
    parser.add_argument("--output", type=str, default="", help="Output graded JSONL path")
    parser.add_argument("--summary", type=str, default="", help="Output summary JSON path")
    parser.add_argument("--limit", type=int, default=0, help="Limit number of rows (0 means all)")
    parser.add_argument("--concurrency", type=int, default=3, help="Gemini grading concurrency")
    parser.add_argument(
        "--resume", type=str, default="",
        help="Path to a partial gemini_graded_*.jsonl to resume from. "
             "Already-graded prompt indices will be skipped.",
    )
    return parser.parse_args()


async def main() -> None:
    args = parse_args()
    timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")

    input_path = Path(args.input) if args.input else _find_latest_input()
    default_out_dir = input_path.parent
    output_path = (
        Path(args.output)
        if args.output
        else default_out_dir / f"gemini_graded_{timestamp}.jsonl"
    )
    summary_path = (
        Path(args.summary)
        if args.summary
        else default_out_dir / f"gemini_graded_summary_{timestamp}.json"
    )
    live_log_path = default_out_dir / f"gemini_grader_live_{timestamp}.log"
    logger = _build_logger(live_log_path)

    # Resume: load already-graded indices from a partial output file
    resume_path = Path(args.resume) if args.resume else None
    already_graded = _load_already_graded(resume_path)
    if already_graded:
        output_path = resume_path  # type: ignore[assignment]
        logger.info(f"[RESUME] Skipping {len(already_graded)} already-graded rows from {resume_path}")

    rows = _load_jsonl(input_path, args.limit)
    if not rows:
        raise RuntimeError(f"No rows loaded from {input_path}")

    pending_count = sum(
        1 for r in rows
        if (r.get("prompt_index") or 0) not in already_graded
    )

    logger.info(f"Input file: {input_path}")
    logger.info(f"Total rows in file: {len(rows)}")
    logger.info(f"Rows to grade (pending): {pending_count}")
    logger.info(f"Concurrency: {args.concurrency}")
    logger.info(f"Per-task timeout: {PER_TASK_TIMEOUT_SECONDS}s")
    logger.info(f"Live log file: {live_log_path}")

    graded_rows = await _grade_rows(
        rows,
        max(1, args.concurrency),
        output_path,
        logger,
        already_graded,
    )

    summary = _summarize(graded_rows)
    summary["input_file"] = str(input_path)
    summary["output_file"] = str(output_path)
    summary["live_log_file"] = str(live_log_path)
    summary["rows_skipped_resume"] = len(already_graded)

    _write_json(summary_path, summary)

    logger.info(f"Graded JSONL: {output_path}")
    logger.info(f"Summary JSON: {summary_path}")
    logger.info(f"Verdicts: {summary['verdicts']}")
    logger.info(f"Average score: {summary['avg_relevancy_score']}")


if __name__ == "__main__":
    asyncio.run(main())
