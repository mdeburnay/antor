"""Client for AnkiConnect HTTP API. Anki must be running with AnkiConnect add-on."""

import requests

from config import ANKI_URL, ANKI_API_VERSION


def _invoke(action: str, **params) -> dict:
    """Send a request to AnkiConnect. Returns the 'result' value or raises on error."""
    payload = {"action": action, "version": ANKI_API_VERSION, "params": params}
    resp = requests.post(ANKI_URL, json=payload, timeout=10)
    resp.raise_for_status()
    data = resp.json()
    if data.get("error") is not None:
        raise RuntimeError(f"AnkiConnect error: {data['error']}")
    return data.get("result")


def get_version() -> int:
    """Returns AnkiConnect API version (e.g. 6)."""
    return _invoke("version")


def sync() -> bool:
    """
    Sync local collection with AnkiWeb. Can take 30–60+ seconds depending on connection.
    Returns True on success. Raises on error.
    """
    payload = {"action": "sync", "version": ANKI_API_VERSION, "params": {}}
    resp = requests.post(ANKI_URL, json=payload, timeout=120)
    resp.raise_for_status()
    data = resp.json()
    if data.get("error") is not None:
        raise RuntimeError(f"AnkiConnect sync error: {data['error']}")
    return True


def get_deck_names() -> list[str]:
    """Return list of all deck names (for deck selector)."""
    return _invoke("deckNames") or []


def create_deck(deck_name: str) -> int:
    """Create a deck with the given name. No-op if it already exists. Returns deck ID."""
    return _invoke("createDeck", deck=deck_name)


def find_notes(query: str) -> list[int]:
    """Find note IDs matching the query (e.g. 'deck:"LLM Flashcards"')."""
    return _invoke("findNotes", query=query)


def notes_info(note_ids: list[int]) -> list[dict]:
    """Get full note data (fields, tags, etc.) for the given note IDs."""
    if not note_ids:
        return []
    return _invoke("notesInfo", notes=note_ids)

def model_field_names(model_name: str) -> list[str]:
    """Get field names for a note type (e.g. ['Front', 'Back'])."""
    return _invoke("modelFieldNames", modelName=model_name)


def add_notes(notes: list[dict]) -> list[int | None]:
    """
    Create notes. Each note: { "deckName": str, "modelName": str, "fields": { "FieldName": "value", ... } }.
    Returns list of new note IDs (or null for failed).
    """
    return _invoke("addNotes", notes=notes)


def get_existing_questions(deck_name: str) -> set[str]:
    """
    Load all notes in the deck and return a set of normalized 'Front' (question) texts
    for duplicate checking. Adjust field name if your note type uses something else.
    """
    query = f'deck:"{deck_name}"'
    note_ids = find_notes(query)
    if not note_ids:
        return set()
    infos = notes_info(note_ids)
    questions = set()
    for info in infos:
        fields = info.get("fields") or {}
        # Common field name for question/front; use modelFieldNames if you use custom type
        front = (fields.get("Front") or fields.get("Question") or {}).get("value", "")
        if front:
            questions.add(_normalize_question(front))
    return questions


def _normalize_question(s: str) -> str:
    """Normalize for duplicate comparison: lowercase, single spaces, strip."""
    return " ".join(s.lower().split()).strip()
