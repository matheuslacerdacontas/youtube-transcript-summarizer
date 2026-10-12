#!/usr/bin/env python3
"""YouTube Transcript Summarizer.

Fetch the *native* transcript of a YouTube video in a given language with the
official Supadata Python SDK, then summarize it with Google Gemini.

Built for iadots.com. Powered by Supadata: https://supadata.ai/r/HHD1MQYC
"""

from __future__ import annotations

import argparse
import json
import os
import sys
import time
from dataclasses import asdict, dataclass
from typing import Optional

from supadata import Supadata, SupadataError
from supadata.types import BatchJob

try:  # python-dotenv is optional
    from dotenv import load_dotenv
except ImportError:  # pragma: no cover
    load_dotenv = None

DEFAULT_MODEL = "gemini-3.8-flash"
DEFAULT_MAX_BYTES = 180_000
POLL_INTERVAL_SECONDS = 2
POLL_TIMEOUT_SECONDS = 180

# Exit codes
EXIT_OK = 0
EXIT_CONFIG = 2
EXIT_SKIPPED = 3
EXIT_ERROR = 1


@dataclass
class Result:
    url: str
    status: str
    requested_lang: str
    transcript_lang: Optional[str] = None
    transcript_chars: Optional[int] = None
    model: Optional[str] = None
    summary: Optional[str] = None
    detail: Optional[str] = None


def base_lang(code: Optional[str]) -> str:
    """'pt-BR' -> 'pt', 'EN' -> 'en'."""
    return str(code or "").strip().lower().replace("_", "-").split("-")[0]


def wait_for_transcript_job(client: Supadata, job_id: str, timeout: int) -> dict:
    """Poll GET /transcript/{jobId} until the async job completes or fails.

    The Supadata API may answer a transcript request with a job id instead of
    the transcript (mostly for large files / generated transcripts). The SDK
    returns a ``BatchJob`` in that case; this helper polls the documented
    ``/transcript/{jobId}`` endpoint through the SDK's own HTTP session.
    """
    deadline = time.monotonic() + timeout
    while True:
        job = client._request("GET", f"/transcript/{job_id}")  # SDK session + auth
        status = job.get("status")
        if status == "completed":
            return job
        if status == "failed":
            err = job.get("error") or {}
            raise SupadataError(
                error=err.get("error", "internal-error"),
                message=err.get("message", "Transcript job failed"),
                details=err.get("details", f"job {job_id} failed"),
            )
        if time.monotonic() > deadline:
            raise TimeoutError(f"Transcript job {job_id} still '{status}' after {timeout}s")
        time.sleep(POLL_INTERVAL_SECONDS)


def fetch_transcript(client: Supadata, url: str, lang: str, timeout: int) -> tuple[str, str]:
    """Return (content, lang) of the native transcript as plain text."""
    transcript = client.transcript(url=url, lang=lang, text=True, mode="native")
    if isinstance(transcript, BatchJob):
        job = wait_for_transcript_job(client, transcript.job_id, timeout)
        content, returned_lang = job.get("content"), job.get("lang", "")
    else:
        content, returned_lang = transcript.content, transcript.lang
    if isinstance(content, list):  # timestamped chunks, just in case
        content = " ".join(getattr(c, "text", None) or c.get("text", "") for c in content)
    return (content or "").strip(), returned_lang or ""


def summarize(text: str, lang: str, model: str, api_key: str, summary_lang: Optional[str]) -> str:
    """Summarize the transcript with Gemini (google-genai SDK)."""
    from google import genai
    from google.genai import types

    target = summary_lang or lang
    client = genai.Client(api_key=api_key)
    response = client.models.generate_content(
        model=model,
        contents=f"Transcript:\n\n{text}",
        config=types.GenerateContentConfig(
            system_instruction=(
                "You summarize YouTube video transcripts for a tech news portal. "
                f"Write the summary in the language with ISO 639-1 code '{target}'. "
                "Use one short intro paragraph followed by 3-5 bullet points with the key "
                "takeaways. Do not invent facts that are not in the transcript."
            ),
            temperature=0.3,
        ),
    )
    summary = (response.text or "").strip()
    if not summary:
        raise RuntimeError("Gemini returned an empty summary")
    return summary


def run(args: argparse.Namespace) -> tuple[Result, int]:
    lang = base_lang(args.lang)
    result = Result(url=args.url, status="started", requested_lang=lang)

    supadata_key = os.getenv("SUPADATA_API_KEY")
    gemini_key = os.getenv("GEMINI_API_KEY")
    missing = [n for n, v in (("SUPADATA_API_KEY", supadata_key),
                              ("GEMINI_API_KEY", gemini_key if not args.transcript_only else "x")) if not v]
    if missing:
        result.status, result.detail = "config_error", "Missing env var(s): " + ", ".join(missing)
        return result, EXIT_CONFIG

    client = Supadata(api_key=supadata_key)
    try:
        content, returned_lang = fetch_transcript(client, args.url, lang, args.timeout)
    except SupadataError as e:
        result.status = "no_transcript"
        result.detail = f"{getattr(e, 'error', 'error')}: {getattr(e, 'message', e)}"
        return result, EXIT_SKIPPED
    except Exception as e:  # network errors, timeouts
        result.status, result.detail = "supadata_error", str(e)
        return result, EXIT_ERROR

    result.transcript_lang = returned_lang
    result.transcript_chars = len(content)

    if base_lang(returned_lang) != lang:
        result.status = "language_mismatch"
        result.detail = f"Asked for '{lang}', got '{returned_lang or 'unknown'}'"
        return result, EXIT_SKIPPED
    if not content:
        result.status, result.detail = "empty_transcript", "Transcript is empty"
        return result, EXIT_SKIPPED
    size = len(content.encode("utf-8"))
    if size > args.max_bytes:
        result.status = "too_long"
        result.detail = f"Transcript is {size} bytes (limit {args.max_bytes})"
        return result, EXIT_SKIPPED

    if args.transcript_only:
        result.status, result.summary = "ok", content
        return result, EXIT_OK

    result.model = args.model
    try:
        result.summary = summarize(content, lang, args.model, gemini_key, args.summary_lang)
    except Exception as e:
        result.status, result.detail = "gemini_error", str(e)
        return result, EXIT_ERROR

    result.status = "ok"
    return result, EXIT_OK


def build_parser() -> argparse.ArgumentParser:
    p = argparse.ArgumentParser(
        prog="summarize.py",
        description="Fetch a YouTube video's native transcript with Supadata and summarize it with Gemini.",
        epilog="Powered by Supadata - https://supadata.ai/r/HHD1MQYC",
    )
    p.add_argument("url", help="YouTube video URL, e.g. https://www.youtube.com/watch?v=VIDEO_ID")
    p.add_argument("-l", "--lang", default="en",
                   help="ISO 639-1 code of the video's original language (default: en)")
    p.add_argument("-s", "--summary-lang", default=None,
                   help="Language for the summary (default: same as --lang)")
    p.add_argument("-m", "--model", default=os.getenv("GEMINI_MODEL", DEFAULT_MODEL),
                   help=f"Gemini model (env GEMINI_MODEL, default: {DEFAULT_MODEL})")
    p.add_argument("--max-bytes", type=int, default=int(os.getenv("MAX_TRANSCRIPT_BYTES", DEFAULT_MAX_BYTES)),
                   help=f"Skip transcripts larger than this (default: {DEFAULT_MAX_BYTES})")
    p.add_argument("--timeout", type=int, default=POLL_TIMEOUT_SECONDS,
                   help=f"Max seconds to wait for an async transcript job (default: {POLL_TIMEOUT_SECONDS})")
    p.add_argument("--transcript-only", action="store_true",
                   help="Only fetch and print the transcript, skip Gemini")
    p.add_argument("--json", action="store_true", help="Print the result as JSON")
    return p


def main(argv: Optional[list[str]] = None) -> int:
    if load_dotenv:
        load_dotenv()
    args = build_parser().parse_args(argv)
    result, code = run(args)

    if args.json:
        print(json.dumps(asdict(result), ensure_ascii=False, indent=2))
    elif result.status == "ok":
        print(result.summary)
    else:
        print(f"[{result.status}] {result.detail}", file=sys.stderr)
    return code


if __name__ == "__main__":
    sys.exit(main())
