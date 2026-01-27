"""Configuration for Anki + Ollama flashcard app."""

# AnkiConnect (Anki must be running with the add-on enabled)
ANKI_URL = "http://127.0.0.1:8765"
ANKI_API_VERSION = 6

# Deck and note type (create these in Anki or use existing)
DECK_NAME = "LLM Flashcards"
NOTE_TYPE = "Basic"  # or create a custom type with fields: Topic, Question, ELI5, Technical

# Ollama
OLLAMA_URL = "http://127.0.0.1:11434"
OLLAMA_MODEL = "llama3.2"
OLLAMA_TIMEOUT_SECONDS = 120

# Generation
CARDS_PER_TOPIC = 5
# Max transcript characters to send to Ollama (avoids context overflow)
MAX_TRANSCRIPT_CHARS = 12000
