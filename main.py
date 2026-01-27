#!/usr/bin/env python3
"""
CLI: generate flashcards for a topic using Ollama, preview, then optionally add to Anki.

Usage:
  python main.py "machine learning"
  python main.py "machine learning" --add   # actually add to Anki after preview
"""

import argparse
import sys

from config import DECK_NAME, NOTE_TYPE, CARDS_PER_TOPIC
from anki_client import get_version, get_existing_questions, add_notes, _normalize_question
from ollama_client import generate_cards


def preview_cards(cards: list[dict], existing: set[str]) -> list[dict]:
    """Mark each card as new or duplicate and return (for display)."""
    result = []
    for c in cards:
        norm = _normalize_question(c["question"])
        result.append({**c, "is_duplicate": norm in existing})
    return result


def print_preview(cards_with_dup: list[dict], topic: str) -> None:
    """Print a simple terminal preview of the cards."""
    print(f"\n--- Preview: {len(cards_with_dup)} cards for topic '{topic}' ---\n")
    for i, c in enumerate(cards_with_dup, 1):
        dup = " (DUPLICATE)" if c["is_duplicate"] else ""
        print(f"[{i}]{dup}")
        print(f"  Q: {c['question']}")
        print(f"  ELI5: {c['eli5'][:120]}{'...' if len(c['eli5']) > 120 else ''}")
        print(f"  Technical: {c['technical'][:120]}{'...' if len(c['technical']) > 120 else ''}")
        print()
    new_count = sum(1 for c in cards_with_dup if not c["is_duplicate"])
    print(f"--- {new_count} new, {len(cards_with_dup) - new_count} duplicates ---\n")


def build_anki_notes(
    cards_with_dup: list[dict],
    topic: str,
    only_new: bool = True,
    deck_name: str | None = None,
) -> list[dict]:
    """Build payload for addNotes. Uses Basic model: Front = question, Back = ELI5 + Technical."""
    deck = (deck_name or DECK_NAME).strip() or DECK_NAME
    notes = []
    for c in cards_with_dup:
        if only_new and c.get("is_duplicate"):
            continue
        back = f"ELI5: {c['eli5']}<br><br>——<br><br>Technical: {c['technical']}"
        notes.append({
            "deckName": deck,
            "modelName": NOTE_TYPE,
            "fields": {
                "Front": c["question"],
                "Back": back,
            },
        })
    return notes


def main() -> None:
    parser = argparse.ArgumentParser(description="Generate flashcards for a topic with Ollama + Anki")
    parser.add_argument("topic", help="Topic to generate 5 flashcards about")
    parser.add_argument("--add", action="store_true", help="Add new cards to Anki after preview")
    args = parser.parse_args()
    topic = args.topic.strip()
    if not topic:
        print("Error: topic is required", file=sys.stderr)
        sys.exit(1)

    # 1) Check AnkiConnect
    try:
        get_version()
    except Exception as e:
        print(f"AnkiConnect not available (is Anki running with the add-on?): {e}", file=sys.stderr)
        sys.exit(1)

    # 2) Load existing questions for duplicate check
    try:
        existing = get_existing_questions(DECK_NAME)
    except Exception as e:
        print(f"Warning: could not load existing cards: {e}. Proceeding without duplicate check.", file=sys.stderr)
        existing = set()

    # 3) Generate cards with Ollama
    print(f"Generating {CARDS_PER_TOPIC} cards for '{topic}' via Ollama...")
    try:
        cards = generate_cards(topic)
    except Exception as e:
        print(f"Ollama error: {e}", file=sys.stderr)
        sys.exit(1)
    if not cards:
        print("No cards returned from Ollama. Check model and prompt.", file=sys.stderr)
        sys.exit(1)

    # 4) Mark duplicates and preview
    cards_with_dup = preview_cards(cards, existing)
    print_preview(cards_with_dup, topic)

    # 5) Optionally add to Anki
    if args.add:
        to_add = build_anki_notes(cards_with_dup, topic, only_new=True)
        if not to_add:
            print("No new cards to add (all duplicates).")
            return
        try:
            ids = add_notes(to_add)
            added = sum(1 for x in ids if x is not None)
            print(f"Added {added} note(s) to deck '{DECK_NAME}'.")
        except Exception as e:
            print(f"Failed to add notes: {e}", file=sys.stderr)
            sys.exit(1)
    else:
        print("Run with --add to add these cards to Anki.")


if __name__ == "__main__":
    main()
