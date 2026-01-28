"""Fetch and extract main article text from a URL. No API key required."""

from trafilatura import fetch_url, extract


def get_article_text(url: str) -> str:
    """
    Fetch the URL and extract the main article body (strips ads, nav, etc.).
    Returns plain text. Raises ValueError with a user-friendly message on failure.
    """
    url = (url or "").strip()
    if not url:
        raise ValueError("Enter an article URL.")

    if not url.startswith(("http://", "https://")):
        raise ValueError("URL must start with http:// or https://")

    try:
        downloaded = fetch_url(url)
    except Exception as e:
        raise ValueError(f"Could not fetch URL: {e}") from e

    if not downloaded:
        raise ValueError("Could not fetch URL (empty or blocked).")

    result = extract(downloaded)
    if not result or not result.strip():
        raise ValueError("No article text could be extracted from this URL (not an article page or unsupported format).")

    return result.strip()
