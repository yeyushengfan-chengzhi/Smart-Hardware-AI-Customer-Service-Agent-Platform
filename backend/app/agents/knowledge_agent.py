"""Product knowledge agent backed by the existing RAG and LLM services."""

from typing import Mapping, Protocol, Sequence

from app.services.llm_service import llm_service
from app.services.rag_service import RAGSearchResult, rag_service
from app.services.source_policy import apply_source_policy, source_label


class KnowledgeRetriever(Protocol):
    def search(self, query: str, top_k: int) -> list[RAGSearchResult]: ...


class AnswerGenerator(Protocol):
    def generate_answer(
        self, query: str, contexts: Sequence[Mapping[str, object]]
    ) -> str: ...


class KnowledgeAgent:
    """Retrieve product documentation and generate a grounded answer."""

    # Map user-facing concepts to terminology commonly used in Chinese and
    # English product manuals.  Expansion improves recall while RAG remains
    # responsible for embedding, scoring, filtering, and ranking.
    CONCEPT_EXPANSIONS = {
        "memory": {
            "aliases": ("ddr5", "ddr4", "内存", "memory", "dimm"),
            "terms": ("内存", "Memory", "DIMM", "规格", "兼容"),
        },
        "cpu": {
            "aliases": ("cpu", "处理器", "processor"),
            "terms": ("CPU", "处理器", "Processor", "插槽", "规格", "兼容"),
        },
        "pcie": {
            "aliases": ("pcie", "pci-e", "pci express"),
            "terms": ("PCIe", "PCI Express", "插槽", "版本", "规格"),
        },
        "m2": {
            "aliases": ("m.2", "m2", "nvme"),
            "terms": ("M.2", "NVMe", "接口", "插槽", "规格"),
        },
        "display_output": {
            "aliases": ("显示输出", "hdmi", "displayport", "dp接口"),
            "terms": ("显示输出", "HDMI", "DisplayPort", "接口", "规格"),
        },
        "power": {
            "aliases": ("功耗", "多少瓦", "供电", "电源"),
            "terms": ("功耗", "供电", "Power", "电源规格", "兼容"),
        },
        "cooling": {
            "aliases": ("水冷", "冷排", "radiator", "water cooling", "aio"),
            "terms": ("水冷", "冷排", "Radiator", "Water Cooling", "240", "280", "360"),
        },
        "case_motherboard": {
            "aliases": ("主板尺寸", "尺寸主板", "机箱支持什么主板"),
            "terms": ("Motherboard", "Form Factor", "ATX", "Micro-ATX", "Mini-ITX"),
        },
    }

    def __init__(
        self,
        retriever: KnowledgeRetriever = rag_service,
        answer_generator: AnswerGenerator = llm_service,
    ) -> None:
        self.retriever = retriever
        self.answer_generator = answer_generator

    def answer(self, query: str, top_k: int = 3) -> dict:
        retrieval_query = self.enhance_query(query)
        contexts = self.retriever.search(query=retrieval_query, top_k=top_k)
        answer = self.answer_generator.generate_answer(query, contexts)
        answer = apply_source_policy(answer, contexts)
        sources = self._sources(contexts)
        return {"query": query, "answer": answer, "sources": sources}

    @classmethod
    def enhance_query(cls, query: str) -> str:
        """Append manual terminology for concepts present in the user query."""
        normalized = query.casefold()
        additions: list[str] = []
        seen = {token.casefold() for token in query.split()}
        for expansion in cls.CONCEPT_EXPANSIONS.values():
            if not any(alias.casefold() in normalized for alias in expansion["aliases"]):
                continue
            for term in expansion["terms"]:
                if term.casefold() not in seen:
                    additions.append(term)
                    seen.add(term.casefold())
        return " ".join((query, *additions)) if additions else query

    @staticmethod
    def _sources(contexts: Sequence[Mapping[str, object]]) -> list[dict]:
        """Return stable source metadata without duplicate document locations."""
        sources: list[dict] = []
        seen: set[tuple[object, object, object, object]] = set()
        for context in contexts:
            key = (
                context.get("filename", ""),
                context.get("page_number"),
                context.get("section_title", ""),
                context.get("source_type", ""),
            )
            if key in seen:
                continue
            seen.add(key)
            sources.append(
                {
                    "filename": str(key[0]),
                    "page_number": key[1],
                    "section_title": str(key[2]),
                    "source_type": str(key[3]),
                    "source_label": source_label(key[3]),
                }
            )
        return sources


knowledge_agent = KnowledgeAgent()
