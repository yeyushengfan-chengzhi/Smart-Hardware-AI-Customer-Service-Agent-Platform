"""Knowledge document extraction, cleaning, section-aware chunking and storage."""

import re
from dataclasses import dataclass
from pathlib import Path

from fastapi import HTTPException, status
from pypdf import PdfReader
from sqlalchemy import delete, select
from sqlalchemy.orm import Session

from app.models.knowledge_chunk import KnowledgeChunk
from app.models.knowledge_document import KnowledgeDocument
from app.services.knowledge_service import BACKEND_DIR, UPLOAD_DIR


TARGET_CHUNK_SIZE = 550
MAX_CHUNK_SIZE = 800
CHUNK_OVERLAP = 100
MIN_USEFUL_LENGTH = 20
URL_RE = re.compile(r"https?://\S+", re.IGNORECASE)
STANDALONE_NUMBERS_RE = re.compile(r"^\s*(?:\d+\s*){1,12}$")


@dataclass(frozen=True)
class ParsedPage:
    page_number: int
    text: str


@dataclass(frozen=True)
class ChunkData:
    content: str
    page_number: int | None
    section_title: str


def _resolve_document_path(document: KnowledgeDocument) -> Path:
    file_path = (BACKEND_DIR / document.file_path).resolve()
    upload_root = UPLOAD_DIR.resolve()
    if not file_path.is_relative_to(upload_root):
        raise HTTPException(status_code=400, detail="invalid document file path")
    if not file_path.is_file():
        raise HTTPException(status_code=404, detail="document file does not exist")
    return file_path


def _read_text_file(file_path: Path) -> str:
    raw = file_path.read_bytes()
    for encoding in ("utf-8-sig", "gb18030"):
        try:
            return raw.decode(encoding)
        except UnicodeDecodeError:
            continue
    raise HTTPException(status_code=422, detail="unable to decode text document")


def clean_text(text: str) -> str:
    """Remove extraction noise while retaining hardware terms and procedures."""
    text = text.replace("\\n", "\n").replace("\r\n", "\n").replace("\r", "\n")
    text = text.replace("⚽", "").replace("\ufeff", "").replace("\u200b", "")
    text = re.sub(r"\.\s*([●•])", r"\1", text)
    text = re.sub(r"\.([A-Z][A-Za-z0-9_-]{2,})\.", r"\1", text)

    seen_urls: set[str] = set()
    cleaned_lines: list[str] = []
    for raw_line in text.splitlines():
        line = re.sub(r"[ \t]+", " ", raw_line).strip()
        if not line or STANDALONE_NUMBERS_RE.fullmatch(line):
            if cleaned_lines and cleaned_lines[-1] != "":
                cleaned_lines.append("")
            continue
        urls = URL_RE.findall(line)
        for url in urls:
            if url in seen_urls or line == url:
                line = line.replace(url, "")
            else:
                seen_urls.add(url)
        line = line.strip(" .")
        if line:
            cleaned_lines.append(line)

    cleaned = "\n".join(cleaned_lines)
    cleaned = re.sub(r"\n{3,}", "\n\n", cleaned).strip()
    return cleaned


def extract_document_pages(document: KnowledgeDocument) -> list[ParsedPage]:
    """Extract a document page-by-page so chunks never cross PDF pages."""
    file_path = _resolve_document_path(document)
    try:
        if document.file_type == "pdf":
            reader = PdfReader(str(file_path))
            return [
                ParsedPage(index, clean_text(page.extract_text() or ""))
                for index, page in enumerate(reader.pages, start=1)
            ]
        if document.file_type in {"txt", "md"}:
            return [ParsedPage(1, clean_text(_read_text_file(file_path)))]
    except HTTPException:
        raise
    except Exception as exc:
        raise HTTPException(status_code=422, detail="unable to parse document") from exc
    raise HTTPException(status_code=400, detail="unsupported document type")


def extract_document_text(document: KnowledgeDocument) -> str:
    """Compatibility helper returning cleaned text for the whole document."""
    return "\n\n".join(page.text for page in extract_document_pages(document) if page.text)


def _is_heading(line: str) -> bool:
    return bool(
        2 <= len(line) <= 48
        and not line.startswith(("●", "•", "⚠", "*", "http"))
        and not re.match(r"^\d+[.、)]", line)
        and not re.search(r"[。；！？:]$", line)
        and not STANDALONE_NUMBERS_RE.fullmatch(line)
    )


def _section_title(text: str) -> str:
    headings: list[str] = []
    for line in text.splitlines()[:5]:
        if _is_heading(line):
            if headings and (len(line) > 30 or re.search(r"[，。；！？]", line)):
                break
            headings.append(line)
            if len(headings) == 2:
                break
        elif headings:
            break
    return " / ".join(headings)


def _split_long_section(text: str, title: str) -> list[str]:
    """Split one page section at paragraph/sentence boundaries with overlap."""
    if len(text) <= MAX_CHUNK_SIZE:
        return [text] if len(text) >= MIN_USEFUL_LENGTH else []

    chunks: list[str] = []
    cursor = 0
    while cursor < len(text):
        limit = min(cursor + MAX_CHUNK_SIZE, len(text))
        if limit < len(text):
            target = min(cursor + TARGET_CHUNK_SIZE, limit)
            boundary = max(
                text.rfind("\n\n", cursor + 200, limit),
                text.rfind("\n", cursor + 200, limit),
                text.rfind("。", cursor + 200, limit),
                text.rfind("；", cursor + 200, limit),
            )
            limit = boundary + 1 if boundary >= target - 150 else limit
        part = text[cursor:limit].strip()
        if title and not part.startswith(title):
            prefix = f"{title}\n"
            part = prefix + part[: MAX_CHUNK_SIZE - len(prefix)]
        if len(part) >= MIN_USEFUL_LENGTH and not URL_RE.fullmatch(part):
            chunks.append(part)
        if limit >= len(text):
            break
        cursor = max(limit - CHUNK_OVERLAP, cursor + 1)
    return chunks


def split_page(text: str, page_number: int) -> list[ChunkData]:
    """Split a cleaned page, preserving its heading and page metadata."""
    text = clean_text(text)
    if not text:
        return []
    title = _section_title(text)
    return [
        ChunkData(content=content, page_number=page_number, section_title=title)
        for content in _split_long_section(text, title)
    ]


def split_text(text: str) -> list[str]:
    """Compatibility wrapper for non-paged callers and tests."""
    return [chunk.content for chunk in split_page(text, 1)]


def build_document_chunks(document: KnowledgeDocument) -> list[ChunkData]:
    return [
        chunk
        for page in extract_document_pages(document)
        for chunk in split_page(page.text, page.page_number)
    ]


def replace_document_chunks(
    db: Session, document_id: int, chunks: list[ChunkData], *, commit: bool = True
) -> list[KnowledgeChunk]:
    db.execute(delete(KnowledgeChunk).where(KnowledgeChunk.document_id == document_id))
    models = [
        KnowledgeChunk(
            document_id=document_id,
            content=chunk.content,
            chunk_index=index,
            page_number=chunk.page_number,
            section_title=chunk.section_title,
        )
        for index, chunk in enumerate(chunks)
    ]
    db.add_all(models)
    db.flush()
    if commit:
        db.commit()
    return models


def parse_document(db: Session, document_id: int) -> int:
    """Extract, clean, split, and atomically replace a document's chunks."""
    document = db.get(KnowledgeDocument, document_id)
    if document is None:
        raise HTTPException(status_code=404, detail="knowledge document does not exist")
    chunks = build_document_chunks(document)
    if not chunks:
        raise HTTPException(status_code=422, detail="document contains no extractable text")
    try:
        replace_document_chunks(db, document_id, chunks)
        document.chunk_count = len(chunks)
        db.commit()
    except Exception:
        db.rollback()
        raise
    return len(chunks)


def list_document_chunks(db: Session, document_id: int) -> list[KnowledgeChunk]:
    if db.get(KnowledgeDocument, document_id) is None:
        raise HTTPException(status_code=404, detail="knowledge document does not exist")
    return list(
        db.scalars(
            select(KnowledgeChunk)
            .where(KnowledgeChunk.document_id == document_id)
            .order_by(KnowledgeChunk.chunk_index.asc())
        ).all()
    )
