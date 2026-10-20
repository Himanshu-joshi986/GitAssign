"""
Minimal Gemini JSON client built on the existing `requests` dependency.

Provider-free design: no SDK, no streaming, no new packages. Deterministic
scoring remains authoritative; this client only powers classification and
domain profiling, and every caller must handle a `None` fallback.

Configuration (environment):
    GEMINI_API_KEY          empty = disabled
    GEMINI_MODEL            default gemini-2.5-flash
    GEMINI_BASE_URL         default https://generativelanguage.googleapis.com/v1beta
    LLM_TIMEOUT_SECONDS     default 60
    LLM_MAX_RETRIES         default 3
    LLM_ENABLED             default true (a key is still required)
    LLM_MAX_ISSUES_PER_RUN  default 50
    LLM_MAX_PROFILES_PER_RUN default 100
"""
import json
import os
import time

import requests

DEFAULT_MODEL = "gemini-2.5-flash"
DEFAULT_BASE_URL = "https://generativelanguage.googleapis.com/v1beta"

# Simple in-process counters for pipeline status (resets on restart).
_stats = {"llm_calls": 0, "llm_failures": 0}


def _env(key: str, default: str = "") -> str:
    return os.environ.get(key, default)


def is_enabled() -> bool:
    """True when the LLM layer is switched on and a key is configured."""
    enabled = _env("LLM_ENABLED", "true").strip().lower() not in ("false", "0", "no", "off")
    return enabled and bool(_env("GEMINI_API_KEY").strip())


def model_name() -> str:
    return _env("GEMINI_MODEL", DEFAULT_MODEL).strip() or DEFAULT_MODEL


def base_url() -> str:
    return _env("GEMINI_BASE_URL", DEFAULT_BASE_URL).rstrip("/")


def call_stats() -> dict:
    """Return the in-process call counters."""
    return dict(_stats)


def reset_stats() -> None:
    _stats["llm_calls"] = 0
    _stats["llm_failures"] = 0


def _strip_fences(text: str) -> str:
    """Remove markdown code fences the model sometimes wraps around JSON."""
    text = text.strip()
    if text.startswith("```"):
        first_newline = text.find("\n")
        if first_newline != -1:
            text = text[first_newline + 1 :]
        if text.rstrip().endswith("```"):
            text = text.rstrip()[:-3]
    return text.strip()


def generate_json(prompt: str, system: str = None) -> dict | None:
    """
    Call Gemini with a JSON-only response contract and return the parsed dict.

    Returns None on permanent failure (missing key, network error, bad JSON,
    or exhausted retries). Retries on HTTP 429/5xx with 1s/2s/4s backoff.
    Never logs the API key or the prompt body.
    """
    api_key = _env("GEMINI_API_KEY").strip()
    if not api_key:
        return None

    model = model_name()
    url = f"{base_url()}/models/{model}:generateContent"

    body: dict = {
        "contents": [{"parts": [{"text": prompt}]}],
        "generationConfig": {
            "temperature": 0.1,
            "responseMimeType": "application/json",
        },
    }
    if system:
        body["systemInstruction"] = {"parts": [{"text": system}]}

    max_retries = max(int(_env("LLM_MAX_RETRIES", "3") or 3), 0)
    timeout = max(int(_env("LLM_TIMEOUT_SECONDS", "60") or 60), 1)

    _stats["llm_calls"] += 1
    for attempt in range(max_retries + 1):
        try:
            response = requests.post(
                url,
                params={"key": api_key},
                json=body,
                timeout=timeout,
            )
        except requests.RequestException as exc:
            _stats["llm_failures"] += 1
            print(f"[llm] model={model} failed: network error ({type(exc).__name__})")
            return None

        if response.status_code in (429, 500, 502, 503, 504) and attempt < max_retries:
            time.sleep(2**attempt)
            continue
        if response.status_code != 200:
            _stats["llm_failures"] += 1
            print(f"[llm] model={model} failed: http {response.status_code}")
            return None

        try:
            payload = response.json()
            text = payload["candidates"][0]["content"]["parts"][0]["text"]
            parsed = json.loads(_strip_fences(text))
        except (ValueError, KeyError, IndexError, TypeError):
            _stats["llm_failures"] += 1
            print(f"[llm] model={model} failed: invalid JSON response")
            return None

        if not isinstance(parsed, dict):
            _stats["llm_failures"] += 1
            print(f"[llm] model={model} failed: response is not a JSON object")
            return None

        print(f"[llm] model={model} ok")
        return parsed

    _stats["llm_failures"] += 1
    print(f"[llm] model={model} failed: retries exhausted")
    return None
