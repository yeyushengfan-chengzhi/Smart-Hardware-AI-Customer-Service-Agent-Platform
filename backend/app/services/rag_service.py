"""Hybrid retrieval and deterministic post-processing for knowledge search."""

import logging
import re
from difflib import SequenceMatcher
from collections.abc import Callable
from typing import TypedDict

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.config import get_settings
from app.database import SessionLocal
from app.models.knowledge_document import KnowledgeDocument
from app.services.knowledge_service import RETRIEVABLE_EMBEDDING_STATUSES
from app.services.vector_service import VectorSearchResult, VectorService, vector_service
from app.services.source_policy import source_label


logger = logging.getLogger(__name__)
MAX_CANDIDATES = 50

CONCEPTS: dict[str, tuple[str, ...]] = {
    "no_display": ("无显示", "没有显示", "没有画面", "黑屏", "display", "video output"),
    "gpu": ("显卡", "gpu", "pcie", "gop", "uefi", "displayport", "hdmi"),
    "memory": ("内存", "dram", "dimm", "ram", "ddr4", "ddr5"),
    "diagnostic": (
        "故障灯",
        "侦错灯",
        "debug led",
        "ez debug led",
        "q-led",
        "q-leds",
        "q led",
        "简易侦错",
        "无法检测",
        "故障",
    ),
    "boot": ("开机", "启动", "post", "无法启动", "启动设备"),
    "cmos": ("cmos", "清除 cmos", "重置 bios", "重启 bios"),
    "power": ("供电", "电源", "cpu_pwr", "atx_pwr"),
    "cpu": ("cpu", "处理器"),
    "bios": ("bios", "bios flashback", "flashback"),
    "cooling": (
        "水冷",
        "冷排",
        "radiator",
        "water cooling",
        "liquid cooling",
        "aio",
    ),
    "case_motherboard": (
        "主板尺寸",
        "尺寸主板",
        "m-atx",
        "matx",
        "atx 机箱",
        "观感",
        "motherboard size",
        "motherboard form factor",
        "case compatibility",
    ),
    "gpu_clearance": (
        "厚显卡",
        "底部风扇",
        "底部进风",
        "显卡长度",
        "挡显卡",
        "空间风险",
    ),
    "cooler_memory": (
        "双塔",
        "高马甲内存",
        "挡内存",
        "顶内存",
        "vrm",
    ),
    "cable_management": ("走线", "理线", "背线", "cable management"),
    "airflow": ("海景房", "风道", "进风", "出风", "airflow"),
}

INTENT_EXPANSIONS: dict[str, tuple[str, ...]] = {
    "no_display": ("gpu", "memory", "diagnostic", "boot", "power", "cpu", "cmos"),
    "diagnostic": ("gpu", "memory", "cpu", "boot"),
}

RETRIEVAL_TERMS: dict[str, str] = {
    "no_display": "无显示 黑屏",
    "gpu": "显卡 GPU",
    "memory": "内存 DRAM",
    "diagnostic": "简易侦错 LED 故障灯 Q-LED",
    "boot": "开机 POST",
    "cmos": "清除 CMOS",
    "power": "主板供电",
    "cpu": "CPU 处理器",
    "bios": "BIOS FlashBack",
    "cooling": "水冷 冷排 radiator water cooling 120 240 280 360",
    "case_motherboard": (
        "机箱主板尺寸 motherboard form factor ATX Micro-ATX Mini-ITX M-ATX ITX"
    ),
    "gpu_clearance": "厚显卡 底部风扇 显卡长度 空间风险 物理干涉",
    "cooler_memory": "双塔风冷 高马甲内存 顶部水冷 VRM 空间 避让",
    "cable_management": "小机箱 装机 走线 理线 背线 空间",
    "airflow": "海景房机箱 风道 进风 出风 散热",
}


class RAGSearchResult(TypedDict):
    chunk_id: int
    document_id: int
    filename: str
    page_number: int | None
    section_title: str
    content: str
    score: float
    semantic_score: float
    keyword_score: float
    source_type: str
    source_label: str


def _contains(text: str, aliases: tuple[str, ...]) -> bool:
    lowered = text.casefold()
    return any(alias.casefold() in lowered for alias in aliases)


def query_concepts(query: str) -> set[str]:
    concepts = {name for name, aliases in CONCEPTS.items() if _contains(query, aliases)}
    expanded = set(concepts)
    for concept in concepts:
        expanded.update(INTENT_EXPANSIONS.get(concept, ()))
    return expanded


def expand_query(query: str, concepts: set[str]) -> str:
    terms = [RETRIEVAL_TERMS[name] for name in sorted(concepts)]
    return f"{query} {' '.join(terms)}" if terms else query


def keyword_score(query: str, content: str, section_title: str = "") -> float:
    """Return a 0-1 generic hardware concept coverage score."""
    concepts = query_concepts(query)
    if not concepts:
        compact_query = re.sub(r"\s+", "", query.casefold())
        return 1.0 if compact_query and compact_query in re.sub(r"\s+", "", content.casefold()) else 0.0
    weighted_hits = 0.0
    for concept in concepts:
        aliases = CONCEPTS[concept]
        if _contains(section_title, aliases):
            weighted_hits += 1.0
        elif _contains(content, aliases):
            weighted_hits += 0.8
    return min(1.0, weighted_hits / len(concepts))


def _text_similarity(left: str, right: str) -> float:
    left = re.sub(r"\s+", "", left.casefold())[:1200]
    right = re.sub(r"\s+", "", right.casefold())[:1200]
    return SequenceMatcher(None, left, right).ratio()


class RAGService:
    def __init__(
        self,
        vectors: VectorService = vector_service,
        similarity_threshold: float | None = None,
        candidate_count: int | None = None,
        active_document_ids_provider: Callable[[], list[int]] | None = None,
        query_document_ids_provider: Callable[[str], list[int]] | None = None,
    ) -> None:
        settings = get_settings()
        self.vectors = vectors
        self.similarity_threshold = settings.similarity_threshold if similarity_threshold is None else similarity_threshold
        self.candidate_count = settings.rag_candidate_count if candidate_count is None else candidate_count
        self.active_document_ids_provider = active_document_ids_provider
        self.query_document_ids_provider = query_document_ids_provider

    def _score(self, query: str, candidate: VectorSearchResult) -> RAGSearchResult:
        semantic = max(0.0, min(1.0, 1.0 - candidate["distance"]))
        lexical = keyword_score(query, candidate["content"], candidate.get("section_title", ""))
        final = semantic * 0.8 + lexical * 0.2
        return {
            "chunk_id": candidate["chunk_id"],
            "document_id": candidate["document_id"],
            "filename": candidate.get("filename", ""),
            "page_number": candidate.get("page_number"),
            "section_title": candidate.get("section_title", ""),
            "content": candidate["content"],
            "score": final,
            "semantic_score": semantic,
            "keyword_score": lexical,
            "source_type": candidate.get("source_type", ""),
            "source_label": source_label(candidate.get("source_type", "")),
        }

    def _deduplicate(self, ranked: list[RAGSearchResult]) -> tuple[list[RAGSearchResult], int]:
        unique: list[RAGSearchResult] = []
        seen_ids: set[int] = set()
        for result in ranked:
            if result["chunk_id"] in seen_ids:
                continue
            duplicate = any(
                result["document_id"] == kept["document_id"]
                and result["page_number"] is not None
                and kept["page_number"] is not None
                and abs(result["page_number"] - kept["page_number"]) <= 1
                and _text_similarity(result["content"], kept["content"]) >= 0.55
                for kept in unique
            )
            if not duplicate:
                unique.append(result)
                seen_ids.add(result["chunk_id"])
        return unique, len(ranked) - len(unique)

    def search(self, query: str, top_k: int) -> list[RAGSearchResult]:
        candidate_count = min(MAX_CANDIDATES, max(top_k * 5, self.candidate_count))
        concepts = query_concepts(query)
        document_ids = (
            self.query_document_ids_provider(query)
            if self.query_document_ids_provider
            else []
        )
        product_scoped = bool(document_ids)
        if not document_ids:
            document_ids = (
                self.active_document_ids_provider()
                if self.active_document_ids_provider
                else None
            )
        if document_ids is None:
            candidates = self.vectors.search(expand_query(query, concepts), candidate_count)
        else:
            candidates = self.vectors.search(
                expand_query(query, concepts), candidate_count, document_ids=document_ids
            )
        scored = sorted(
            (self._score(query, candidate) for candidate in candidates),
            key=lambda result: result["score"],
            reverse=True,
        )
        if product_scoped:
            for result in scored:
                if result["semantic_score"] >= 0.20:
                    result["score"] = max(
                        result["score"],
                        min(
                            1.0,
                            self.similarity_threshold
                            + 0.02
                            + result["semantic_score"] * 0.05,
                        ),
                    )
            relevant = [
                result for result in scored if result["semantic_score"] >= 0.20
            ]
        else:
            relevant = [
                result
                for result in scored
                if result["score"] >= self.similarity_threshold
                and (not concepts or result["keyword_score"] > 0.0)
            ]
        deduplicated, duplicate_count = self._deduplicate(relevant)
        results = deduplicated[:top_k]

        logger.info(
            "RAG search query=%r product_scoped=%s candidates=%d "
            "threshold_filtered=%d deduplicated=%d returned=%d",
            query, product_scoped, len(candidates), len(scored) - len(relevant),
            duplicate_count, len(results),
        )
        for result in results:
            logger.info(
                "RAG result chunk_id=%d section=%r semantic=%.4f keyword=%.4f final=%.4f",
                result["chunk_id"], result["section_title"], result["semantic_score"],
                result["keyword_score"], result["score"],
            )
        return results


def _active_document_ids() -> list[int]:
    with SessionLocal() as db:
        return _active_document_ids_from_db(db)


def _active_document_ids_from_db(db: Session) -> list[int]:
    return list(db.scalars(select(KnowledgeDocument.id).where(
        KnowledgeDocument.status == "active",
        KnowledgeDocument.embedding_status.in_(RETRIEVABLE_EMBEDDING_STATUSES),
    )).all())


def _normalized_identity(value: str) -> str:
    return "".join(character for character in value.casefold() if character.isalnum())


def _matching_active_document_ids_from_db(db: Session, query: str) -> list[int]:
    """Match product, vendor and filenames before semantic retrieval."""
    normalized_query = "".join(
        character for character in query.casefold() if character.isalnum()
    )
    if not normalized_query:
        return []
    candidates = db.execute(
        select(
            KnowledgeDocument.id,
            KnowledgeDocument.vendor,
            KnowledgeDocument.product_name,
            KnowledgeDocument.filename,
            KnowledgeDocument.original_filename,
        ).where(
            KnowledgeDocument.status == "active",
            KnowledgeDocument.embedding_status.in_(RETRIEVABLE_EMBEDDING_STATUSES),
        )
    ).all()
    matches: list[tuple[int, int]] = []
    for document_id, vendor, product_name, filename, original_filename in candidates:
        normalized_vendor = _normalized_identity(vendor or "")
        normalized_product = _normalized_identity(product_name or "")
        normalized_vendor_product = f"{normalized_vendor}{normalized_product}"
        normalized_filenames = [
            _normalized_identity(filename or ""),
            _normalized_identity(original_filename or ""),
        ]
        strengths: list[int] = []
        if len(normalized_product) >= 3 and normalized_product in normalized_query:
            strengths.append(len(normalized_product))
        if (
            len(normalized_vendor_product) >= 4
            and normalized_vendor_product in normalized_query
        ):
            strengths.append(len(normalized_vendor_product))
        if len(normalized_vendor) >= 3 and normalized_vendor in normalized_query:
            strengths.append(len(normalized_vendor))
        for normalized_filename in normalized_filenames:
            if len(normalized_filename) >= 6 and normalized_filename in normalized_query:
                strengths.append(len(normalized_filename))
            elif (
                len(normalized_query) >= 6
                and normalized_query in normalized_filename
            ):
                strengths.append(len(normalized_query))
        if strengths:
            matches.append((document_id, max(strengths)))
    if not matches:
        return []
    longest_match = max(length for _, length in matches)
    return [
        document_id
        for document_id, length in matches
        if length == longest_match
    ]


def _matching_active_document_ids(query: str) -> list[int]:
    with SessionLocal() as db:
        return _matching_active_document_ids_from_db(db, query)


rag_service = RAGService(
    active_document_ids_provider=_active_document_ids,
    query_document_ids_provider=_matching_active_document_ids,
)
