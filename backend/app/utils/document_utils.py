import logging
from html.parser import HTMLParser

logger = logging.getLogger(__name__)

_BLOCK_END_TAGS = {"p", "h1", "h2", "h3", "h4", "li", "div", "ul", "ol", "br", "tr", "section", "article"}
_LIST_ITEM_TAGS = {"li"}


class _TextExtractor(HTMLParser):
    def __init__(self) -> None:
        super().__init__()
        self.parts: list[str] = []

    def handle_starttag(self, tag: str, attrs: list[tuple[str, str | None]]) -> None:
        if tag in _LIST_ITEM_TAGS:
            self.parts.append("\n- ")

    def handle_startendtag(self, tag: str, attrs: list[tuple[str, str | None]]) -> None:
        if tag == "br":
            self.parts.append("\n")

    def handle_endtag(self, tag: str) -> None:
        if tag in _BLOCK_END_TAGS:
            self.parts.append("\n")

    def handle_data(self, data: str) -> None:
        if data.strip():
            self.parts.append(data)


def html_to_text(raw: str | None) -> str:
    """Convert HTML job descriptions to readable plain text (headings/lists become newlines + bullets)."""
    if not raw:
        return raw or ""
    parser = _TextExtractor()
    try:
        parser.feed(raw)
        parser.close()
    except Exception as e:
        logger.warning("HTML conversion failed, returning raw text: %s", e)
        return raw
    text = "".join(parser.parts)
    lines = [line.rstrip() for line in text.splitlines()]
    cleaned = "\n".join(line for line in lines if line.strip() or line == "")
    return "\n".join(line.rstrip() for line in cleaned.splitlines()).strip()


def extract_text_from_path(path: str) -> str:
    lower = path.lower()
    if lower.endswith(".pdf"):
        try:
            import pdfplumber

            with pdfplumber.open(path) as pdf:
                pages = []
                for page in pdf.pages:
                    pages.append(page.extract_text() or "")
                return "\n".join(pages)
        except Exception as e:
            logger.error("PDF extraction failed for %s: %s", path, e)
            raise ValueError(f"Could not extract text from PDF: {e}") from e

    if lower.endswith(".docx"):
        try:
            import docx

            document = docx.Document(path)
            return "\n".join(p.text for p in document.paragraphs)
        except Exception as e:
            logger.error("DOCX extraction failed for %s: %s", path, e)
            raise ValueError(f"Could not extract text from DOCX: {e}") from e

    raise ValueError("Unsupported file type. Only PDF and DOCX are supported.")
