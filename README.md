# Antor

Generate flashcards on a topic using a local LLM (Ollama) and add them to Anki via AnkiConnect.

## Setup

1. **Anki + AnkiConnect**

   - Install [Anki](https://apps.ankiweb.net/).
   - Install the [AnkiConnect](https://foosoft.net/projects/anki-connect/) add-on (Anki → Tools → Add-ons → Get Add-ons, use the code from the add-on page).
   - Create a deck (e.g. "LLM Flashcards") or use the default deck name in `config.py`.

2. **Ollama**

   - [Download Ollama](https://ollama.com/) and install.
   - Pull a model, e.g.: `ollama pull llama3.2`
   - Set `OLLAMA_MODEL` in `config.py` to match.

3. **Python** (3.9–3.13; Streamlit does not support 3.14 yet.)
   - If Homebrew gave you Python 3.14, install 3.12 and use it for this project:
     ```bash
     brew install python@3.12
     cd /path/to/antor
     rm -rf venv
     /opt/homebrew/opt/python@3.12/bin/python3.12 -m venv venv
     ./venv/bin/pip install -r requirements.txt
     ```
   - Then run with `./run.sh` or `./venv/bin/python -m streamlit run app.py`.
   - Or, with any supported Python: `python3 -m pip install -r requirements.txt` then `python3 -m streamlit run app.py`.

## Spinning up Antor

**Order that works:** Anki first → then Ollama (if you use it) → then Antor.

1. **Start Anki** and leave it open (AnkiConnect must be enabled).
2. **Start Ollama** (often already running; if not, start the Ollama app or run `ollama serve`).
3. **Start Antor** from the project directory:
   ```bash
   python3 -m streamlit run app.py
   ```
   The app will open in your browser (usually http://localhost:8501).

**Anki check:** When the Streamlit app loads, it checks whether Anki (with AnkiConnect) is reachable. If not, you’ll see a warning at the top. Start Anki and reload the page.

**Script (macOS/Linux):** From the project root you can run:

```bash
chmod +x run.sh && ./run.sh
```

or `bash run.sh`. This opens Anki (on macOS), waits a few seconds, then starts Streamlit. On other systems, start Anki yourself and run `python3 -m streamlit run app.py`.

## Usage

### Web UI (Streamlit)

1. Have Anki and Ollama running (see “Spinning up Antor” above).
2. From the project directory:
   ```bash
   python3 -m streamlit run app.py
   ```
3. Open the URL in your browser (usually http://localhost:8501).
4. **By topic:** enter a topic, click **Generate**. **From YouTube:** paste a video URL, click **Fetch transcript & generate cards**. **From URL:** paste an article URL, click **Fetch article & generate cards**. In all cases, review the preview and click **Add to Anki** to add new cards (duplicates are skipped).

### CLI

- **Preview only** (generate cards, show them, do not add to Anki):
  ```bash
  python main.py "machine learning"
  ```
- **Preview and add** new cards to Anki (duplicates are skipped):
  ```bash
  python main.py "machine learning" --add
  ```

Ensure Anki is running (with AnkiConnect enabled) before using `--add` or duplicate checking.

## Config

Edit `config.py` to change:

- `DECK_NAME` – Anki deck to add cards to
- `NOTE_TYPE` – Anki note type (default `"Basic"` with Front/Back)
- `OLLAMA_MODEL` – e.g. `llama3.2`, `mistral`
- `CARDS_PER_TOPIC` – number of cards to generate per run
- `MAX_TRANSCRIPT_CHARS` – max characters of YouTube transcript sent to Ollama (default 12000)

## Project layout

- `run.sh` – optional: start Anki then Streamlit (macOS: opens Anki; run `./run.sh` from project root)
- `config.py` – settings
- `anki_client.py` – AnkiConnect API (find notes, add notes, etc.)
- `ollama_client.py` – Ollama chat API and JSON parsing (topic + transcript)
- `youtube_client.py` – YouTube transcript fetch (no API key)
- `article_client.py` – Article text extraction from URLs (trafilatura)
- `main.py` – CLI: topic → generate → preview → optional add
- `app.py` – Streamlit UI: by topic, from YouTube, deck choice, sync
