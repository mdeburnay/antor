"""
Streamlit UI for generating flashcards with Ollama and adding them to Anki.
Run with: streamlit run app.py
"""

import streamlit as st

from config import DECK_NAME, CARDS_PER_TOPIC
from anki_client import get_version, get_deck_names, get_existing_questions, add_notes, sync, create_deck
from ollama_client import generate_cards, generate_cards_from_transcript

# Card style values (must match ollama_client.CARD_STYLE_*)
CARD_STYLE_ELI5 = "eli5_technical"
CARD_STYLE_CODE = "code"
from main import preview_cards, build_anki_notes, _is_code_style_card
from youtube_client import get_transcript
from article_client import get_article_text

st.set_page_config(page_title="Antor — Flashcard generator", layout="centered")
st.title("Antor")
st.caption("Generate flashcards with Ollama → preview → add to Anki")

# Check Anki + AnkiConnect on load so the user sees status before trying to generate/add
anki_ok = True
try:
    get_version()
    deck_names = get_deck_names()
except Exception:
    anki_ok = False
    deck_names = []
if not anki_ok:
    st.warning(
        "**Anki doesn’t appear to be running** (or AnkiConnect isn’t enabled). "
        "Start Anki, ensure the add-on is active, then reload this page. "
        "Generate and Add to Anki need Anki to be up."
    )

# Deck selector: existing decks from Anki or new deck name
NEW_DECK_OPTION = "➕ New deck…"
deck_choices = deck_names + [NEW_DECK_OPTION]
default_idx = 0
if deck_names and DECK_NAME in deck_names:
    default_idx = deck_names.index(DECK_NAME)
elif not deck_choices:
    deck_choices = [NEW_DECK_OPTION]

def normalize_topic(s: str) -> str:
    """Strip and normalize so we send the same string to Ollama as from the CLI."""
    if not s:
        return ""
    # Normalize common unicode space-like chars to ASCII space (browser paste can add these)
    for ch in ("\u00a0", "\u2003", "\u2002", "\ufeff"):
        s = s.replace(ch, " ")
    return " ".join(s.split()).strip()

# Deck: choose existing or new
selected_deck_option = st.selectbox(
    "Deck",
    options=deck_choices,
    index=min(default_idx, len(deck_choices) - 1),
    help="Choose an existing deck or create a new one. Duplicate check and Add use this deck.",
)
if selected_deck_option == NEW_DECK_OPTION:
    new_deck_name = st.text_input("New deck name", value=DECK_NAME, placeholder="e.g. My New Deck")
    deck_to_use = normalize_topic(new_deck_name or "") or DECK_NAME
else:
    deck_to_use = selected_deck_option

# Card style: ELI5/Technical or Code snippet
CARD_STYLE_LABELS = {"eli5_technical": "ELI5 / Technical", "code": "Code snippet (question + code + answer)"}
card_style = st.radio(
    "Card style",
    options=[CARD_STYLE_ELI5, CARD_STYLE_CODE],
    format_func=lambda x: CARD_STYLE_LABELS[x],
    horizontal=True,
    key="card_style",
)

if "cards" not in st.session_state:
    st.session_state.cards = None
if "topic_used" not in st.session_state:
    st.session_state.topic_used = None
if "deck_used" not in st.session_state:
    st.session_state.deck_used = None

tab_topic, tab_youtube, tab_url = st.tabs(["By topic", "From YouTube", "From URL"])

with tab_topic:
    topic_input = st.text_input("Topic", placeholder="e.g. machine learning", label_visibility="collapsed", key="topic_input")
    topic = normalize_topic(topic_input or "")
    generate_clicked = st.button("Generate", type="primary", key="btn_generate")

with tab_youtube:
    youtube_url_input = st.text_input(
        "YouTube URL",
        placeholder="https://www.youtube.com/watch?v=... or https://youtu.be/...",
        label_visibility="collapsed",
        key="youtube_url",
    )
    youtube_url = (youtube_url_input or "").strip()
    youtube_clicked = st.button("Fetch transcript & generate cards", type="primary", key="btn_youtube")

with tab_url:
    article_url_input = st.text_input(
        "Article URL",
        placeholder="https://example.com/article or any article link",
        label_visibility="collapsed",
        key="article_url",
    )
    article_url = (article_url_input or "").strip()
    url_clicked = st.button("Fetch article & generate cards", type="primary", key="btn_article_url")

def run_generate(topic_to_use: str, deck_name: str):
    """Generate cards for the given topic and deck (passed explicitly for click-time values)."""
    if not topic_to_use:
        st.error("Enter a topic.")
        return
    if not deck_name:
        st.error("Enter or select a deck.")
        return
    with st.status("Generating cards…", expanded=True) as status:
        try:
            get_version()
        except Exception as e:
            st.error(f"AnkiConnect not available. Is Anki running with the add-on? {e}")
            status.update(label="Error", state="error")
            return
        try:
            existing = get_existing_questions(deck_name)
        except Exception:
            existing = set()
        st.write(f"Generating {CARDS_PER_TOPIC} cards for “{topic_to_use}” → deck “{deck_name}” …")
        try:
            cards = generate_cards(topic_to_use, card_style=card_style)
        except Exception as e:
            st.error(f"Ollama error: {e}")
            status.update(label="Error", state="error")
            return
        if not cards:
            st.error("No cards returned. Check model and prompt.")
            status.update(label="Error", state="error")
            return
        cards_with_dup = preview_cards(cards, existing)
        st.session_state.cards = cards_with_dup
        st.session_state.topic_used = topic_to_use
        st.session_state.deck_used = deck_name
        new_count = sum(1 for c in cards_with_dup if not c["is_duplicate"])
        status.update(label=f"Done — {len(cards_with_dup)} cards ({new_count} new) → “{deck_name}”", state="complete")

def run_youtube(youtube_url_to_use: str, deck_name: str):
    """Fetch transcript and generate cards from YouTube video."""
    if not youtube_url_to_use:
        st.error("Enter a YouTube URL.")
        return
    if not deck_name:
        st.error("Enter or select a deck.")
        return
    with st.status("Fetching transcript & generating cards…", expanded=True) as status:
        try:
            get_version()
        except Exception as e:
            st.error(f"AnkiConnect not available. Is Anki running with the add-on? {e}")
            status.update(label="Error", state="error")
            return
        try:
            transcript = get_transcript(youtube_url_to_use)
        except ValueError as e:
            st.error(str(e))
            status.update(label="Error", state="error")
            return
        status.update(label="Transcript fetched. Generating cards…", state="running")
        try:
            existing = get_existing_questions(deck_name)
        except Exception:
            existing = set()
        try:
            cards = generate_cards_from_transcript(transcript, card_style=card_style)
        except Exception as e:
            st.error(f"Ollama error: {e}")
            status.update(label="Error", state="error")
            return
        if not cards:
            st.error("No cards returned. Check model and prompt.")
            status.update(label="Error", state="error")
            return
        cards_with_dup = preview_cards(cards, existing)
        st.session_state.cards = cards_with_dup
        st.session_state.topic_used = "YouTube video"
        st.session_state.deck_used = deck_name
        new_count = sum(1 for c in cards_with_dup if not c["is_duplicate"])
        status.update(label=f"Done — {len(cards_with_dup)} cards ({new_count} new) → “{deck_name}”", state="complete")

def run_article_url(url_to_use: str, deck_name: str):
    """Fetch article, extract main text, and generate cards from it."""
    if not url_to_use:
        st.error("Enter an article URL.")
        return
    if not deck_name:
        st.error("Enter or select a deck.")
        return
    with st.status("Fetching article & generating cards…", expanded=True) as status:
        try:
            get_version()
        except Exception as e:
            st.error(f"AnkiConnect not available. Is Anki running with the add-on? {e}")
            status.update(label="Error", state="error")
            return
        try:
            text = get_article_text(url_to_use)
        except ValueError as e:
            st.error(str(e))
            status.update(label="Error", state="error")
            return
        status.update(label="Article fetched. Generating cards…", state="running")
        try:
            existing = get_existing_questions(deck_name)
        except Exception:
            existing = set()
        try:
            cards = generate_cards_from_transcript(text, card_style=card_style)
        except Exception as e:
            st.error(f"Ollama error: {e}")
            status.update(label="Error", state="error")
            return
        if not cards:
            st.error("No cards returned. Check model and prompt.")
            status.update(label="Error", state="error")
            return
        cards_with_dup = preview_cards(cards, existing)
        st.session_state.cards = cards_with_dup
        st.session_state.topic_used = "Article"
        st.session_state.deck_used = deck_name
        new_count = sum(1 for c in cards_with_dup if not c["is_duplicate"])
        status.update(label=f"Done — {len(cards_with_dup)} cards ({new_count} new) → “{deck_name}”", state="complete")

if generate_clicked:
    topic = normalize_topic(st.session_state.get("topic_input") or "")
    run_generate(topic, deck_to_use)
if youtube_clicked:
    run_youtube(youtube_url, deck_to_use)
if url_clicked:
    run_article_url(article_url, deck_to_use)

col1, col2, _ = st.columns([1, 1, 3])
with col1:
    add_clicked = st.button("Add to Anki", disabled=(st.session_state.cards is None))
with col2:
    sync_clicked = st.button("Sync")

if sync_clicked:
    with st.status("Syncing with AnkiWeb…", expanded=True) as status:
        try:
            sync()
            status.update(label="Sync complete", state="complete")
            st.success("Synced with AnkiWeb.")
        except Exception as e:
            st.error(f"Sync failed: {e}")
            status.update(label="Sync failed", state="error")

if st.session_state.cards:
    # Show current deck so user sees where cards will go if they click Add (add uses current selection)
    st.subheader(f"Preview → will add to “{deck_to_use}”")
    for i, c in enumerate(st.session_state.cards, 1):
        label = f"Card {i}: {c['question'][:50]}{'…' if len(c['question']) > 50 else ''}"
        if c.get("is_duplicate"):
            label += " — duplicate"
        with st.expander(label, expanded=(i == 1)):
            st.markdown("**Question**")
            st.write(c["question"])
            if _is_code_style_card(c):
                st.markdown("**Code**")
                st.code(c["code"], language=None)
                st.markdown("**Answer**")
                st.write(c["answer"])
            else:
                st.markdown("**ELI5**")
                st.write(c["eli5"])
                st.markdown("**Technical**")
                st.write(c["technical"])

    if add_clicked:
        # Use current deck selection so changing deck before Add sends cards to the new deck
        add_deck = deck_to_use
        to_add = build_anki_notes(
            st.session_state.cards,
            st.session_state.topic_used or "",
            only_new=True,
            deck_name=add_deck,
        )
        if not to_add:
            st.info("No new cards to add (all duplicates).")
        else:
            try:
                create_deck(add_deck)  # ensure deck exists (no-op if already there)
                ids = add_notes(to_add)
                added = sum(1 for x in ids if x is not None)
                st.success(f"Added {added} note(s) to deck “{add_deck}”.")
            except Exception as e:
                st.error(f"Failed to add notes: {e}")
