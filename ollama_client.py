"""Client for Ollama chat API to generate flashcard content."""

import json
import re

import requests

from config import (
    OLLAMA_URL,
    OLLAMA_MODEL,
    OLLAMA_TIMEOUT_SECONDS,
    CARDS_PER_TOPIC,
    MAX_TRANSCRIPT_CHARS,
)


SYSTEM_PROMPT = """You generate flashcard content. For each card output:
- question: one short question or prompt
- eli5: a 2-3 sentence explanation in plain language (ELI5 style)
- technical: a 2-4 sentence precise technical explanation

Be concise. Output exactly one JSON array of objects with keys: question, eli5, technical.
Use double quotes for all JSON keys and string values. No markdown, no text before or after the array."""


def generate_cards(topic: str) -> list[dict]:
    """
    Ask Ollama to generate CARDS_PER_TOPIC flashcards for the given topic.
    Returns a list of dicts with keys: question, eli5, technical.
    """
    user_prompt = f"Generate exactly {CARDS_PER_TOPIC} flashcards about: {topic}"
    url = f"{OLLAMA_URL.rstrip('/')}/api/chat"
    payload = {
        "model": OLLAMA_MODEL,
        "messages": [
            {"role": "system", "content": SYSTEM_PROMPT},
            {"role": "user", "content": user_prompt},
        ],
        "stream": False,
    }
    resp = requests.post(url, json=payload, timeout=OLLAMA_TIMEOUT_SECONDS)
    resp.raise_for_status()
    data = resp.json()
    content = (data.get("message") or {}).get("content") or ""
    if not content.strip():
        raise ValueError(
            "Ollama returned an empty response. Is the model running? Try: ollama list"
        )
    cards = _parse_cards_json(content)
    if not cards:
        snippet = (content[:500] + "..." if len(content) > 500 else content).replace("\n", " ")
        raise ValueError(
            f"Parsed 0 cards from Ollama response. First 500 chars: {snippet!r}"
        )
    return cards


def generate_cards_from_transcript(transcript: str) -> list[dict]:
    """
    Generate CARDS_PER_TOPIC flashcards from YouTube (or other) transcript text.
    Transcript is truncated to MAX_TRANSCRIPT_CHARS to fit model context.
    Returns same shape as generate_cards: list of dicts with question, eli5, technical.
    """
    text = (transcript or "").strip()
    if not text:
        raise ValueError("Transcript text is empty.")
    if len(text) > MAX_TRANSCRIPT_CHARS:
        text = text[:MAX_TRANSCRIPT_CHARS] + "\n\n[Transcript truncated for length.]"
    user_prompt = (
        f"From the following transcript, generate exactly {CARDS_PER_TOPIC} flashcards. "
        "Base each card on concrete facts or ideas from the transcript. "
        "For each card output: question, eli5, technical (same JSON format as before).\n\n"
        "Transcript:\n\n"
        f"{text}"
    )
    url = f"{OLLAMA_URL.rstrip('/')}/api/chat"
    payload = {
        "model": OLLAMA_MODEL,
        "messages": [
            {"role": "system", "content": SYSTEM_PROMPT},
            {"role": "user", "content": user_prompt},
        ],
        "stream": False,
    }
    resp = requests.post(url, json=payload, timeout=OLLAMA_TIMEOUT_SECONDS)
    resp.raise_for_status()
    data = resp.json()
    content = (data.get("message") or {}).get("content") or ""
    if not content.strip():
        raise ValueError(
            "Ollama returned an empty response. Is the model running? Try: ollama list"
        )
    cards = _parse_cards_json(content)
    if not cards:
        snippet = (content[:500] + "..." if len(content) > 500 else content).replace("\n", " ")
        raise ValueError(
            f"Parsed 0 cards from Ollama response. First 500 chars: {snippet!r}"
        )
    return cards


def _parse_cards_json(raw: str) -> list[dict]:
    """Parse LLM output into a list of card dicts. Strips markdown code fences if present."""
    text = raw.strip()
    # Remove optional ```json ... ``` wrapper
    match = re.search(r"```(?:json)?\s*([\s\S]*?)\s*```", text)
    if match:
        text = match.group(1).strip()

    parsed = None
    try:
        parsed = json.loads(text)
    except json.JSONDecodeError:
        # Try to extract a JSON array: first '[' to last ']' (handles preamble/extra text)
        start = text.find("[")
        end = text.rfind("]")
        if start != -1 and end != -1 and end > start:
            try:
                parsed = json.loads(text[start : end + 1])
            except json.JSONDecodeError:
                # Repair: model sometimes outputs [ "question": "...", "eli5": "...", "technical": "...", "question": ... ] (array with object-style pairs but no {})
                repaired = _repair_array_of_objects(text[start : end + 1])
                if repaired:
                    try:
                        parsed = json.loads(repaired)
                    except json.JSONDecodeError:
                        pass

    if parsed is None:
        parsed = _parse_flat_key_value_array(text)
    if parsed is None:
        # Fallback: extract "question": "..", "eli5": "..", "technical": ".." by scanning (handles broken array-with-object-keys format)
        parsed = _parse_array_like_key_value_text(text)
    if parsed is None:
        snippet = (raw[:500] + "..." if len(raw) > 500 else raw).replace("\n", " ")
        raise ValueError(
            f"Ollama returned invalid JSON. First 500 chars: {snippet!r}"
        ) from None

    if not isinstance(parsed, list):
        parsed = [parsed]
    # Normalize keys to question, eli5, technical
    cards = []
    for i, item in enumerate(parsed):
        if not isinstance(item, dict):
            continue
        cards.append({
            "question": str(item.get("question", item.get("Question", ""))).strip(),
            "eli5": str(item.get("eli5", item.get("elI5", item.get("ELI5", "")))).strip(),
            "technical": str(item.get("technical", item.get("Technical", ""))).strip(),
        })
    return cards


def _repair_array_of_objects(s: str) -> str | None:
    """If the model output [ \"question\": \"...\", \"eli5\": ..., \"technical\": ... ] (no {} per object), insert them."""
    s = s.strip()
    if not s.startswith("["):
        return None
    if not s.endswith("]"):
        s = s + "]"
    if not re.search(r'"[Qq]uestion"\s*:', s):
        return None
    # Insert { after [ so we get [ {"question":
    repaired = re.sub(r'\[\s*"[Qq]uestion"', '[ {"question"', s, count=1)
    # Between cards: comma or newline then "question": -> }, { "question": (comma between array elements)
    repaired = re.sub(r'(?:,\s*|[\n\r]+\s*)"[Qq]uestion"\s*:', r'}, { "question":', repaired)
    # Close last object: insert } before final ] (avoid duplicating the closing quote)
    repaired = re.sub(r'(\s*)\](\s*)$', r'\1 } \2]', repaired)
    return repaired


def _extract_quoted_value(s: str, after_open_quote: int) -> tuple[str | None, int]:
    """Return (value, position_after_closing_quote) or (None, after_open_quote). after_open_quote is index of the opening \"."""
    i = after_open_quote
    if i >= len(s) or s[i] != '"':
        return None, after_open_quote
    i += 1
    start = i
    while i < len(s):
        if s[i] == '\\' and i + 1 < len(s):
            i += 2
            continue
        if s[i] == '"':
            value = s[start:i].replace('\\"', '"').replace('\\\\', '\\')
            return value, i + 1
        i += 1
    return None, after_open_quote


def _parse_array_like_key_value_text(text: str) -> list[dict] | None:
    """Parse when model outputs [ \"question\": \"Q?\", \"eli5\": \"E\", \"technical\": \"T\", \"question\": ... ] by scanning for key/value pairs."""
    start = text.find("[")
    end = text.rfind("]")
    if start == -1 or end <= start:
        return None
    s = text[start : end + 1]
    cards = []
    # Keys we look for (regex for flexibility)
    key_pattern = re.compile(r'"(?:question|Question|eli5|elI5|ELI5|technical|Technical)"\s*:\s*"', re.IGNORECASE)
    pos = 0
    while pos < len(s):
        m = key_pattern.search(s, pos)
        if not m:
            break
        key_span = m.group(0)
        key_name = key_span.split('"')[1].lower()
        value_start = m.end() - 1  # index of the opening " before the value
        value, after = _extract_quoted_value(s, value_start)
        if value is None:
            pos = m.end()
            continue
        pos = after
        if key_name == "question":
            # Start of a new card
            cards.append({"question": value, "eli5": "", "technical": ""})
        elif cards and key_name == "eli5":
            cards[-1]["eli5"] = value
        elif cards and key_name == "technical":
            cards[-1]["technical"] = value
    return cards if cards and any(c.get("technical") or c.get("question") for c in cards) else None


def _parse_flat_key_value_array(text: str) -> list[dict] | None:
    """Parse when model returns e.g. ["question","Q","elI5","E","technical","T"], ["question", ...]. Merges into one flat array and builds cards from key-value pairs."""
    # Merge separate arrays into one: "], [" or "] [" (no comma) -> ", "
    merged = re.sub(r"\]\s*,?\s*\[", ", ", text)
    start, end = merged.find("["), merged.rfind("]")
    if start == -1 or end == -1 or end <= start:
        return None
    try:
        flat = json.loads(merged[start : end + 1])
    except json.JSONDecodeError:
        return None
    if not isinstance(flat, list) or not flat:
        return None
    # Keys: model sometimes outputs "elI5"; we treat as "eli5"
    cards = []
    current = {}
    i = 0
    while i < len(flat):
        val = flat[i]
        if not isinstance(val, str):
            i += 1
            continue
        key_cand = val.lower()
        if key_cand not in ("question", "eli5", "technical"):
            i += 1
            continue
        key = "eli5" if key_cand == "eli5" else key_cand
        i += 1
        if i >= len(flat):
            break
        if key == "question":
            if current and (current.get("question") or current.get("technical")):
                cards.append(current)
            current = {"question": "", "eli5": "", "technical": ""}
        if not current:
            current = {"question": "", "eli5": "", "technical": ""}
        if isinstance(flat[i], str):
            current[key] = flat[i]
        i += 1
    if current and (current.get("question") or current.get("technical")):
        cards.append(current)
    return cards if cards else None
