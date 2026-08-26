"""Sentence embedding service for Chinese knowledge text."""

from threading import Lock

from sentence_transformers import SentenceTransformer


class EmbeddingService:
    """Lazily load BGE and encode batches of text into dense vectors."""

    MODEL_NAME = "BAAI/bge-small-zh-v1.5"

    def __init__(self, model_name: str = MODEL_NAME) -> None:
        self.model_name = model_name
        self._model: SentenceTransformer | None = None
        self._load_lock = Lock()

    def _get_model(self) -> SentenceTransformer:
        """Load the model once, on the first embedding request."""
        if self._model is None:
            with self._load_lock:
                if self._model is None:
                    # Knowledge processing is an offline workflow. The model
                    # must be provisioned in the local Hugging Face cache; do
                    # not probe or download from the network at runtime.
                    self._model = SentenceTransformer(
                        self.model_name,
                        local_files_only=True,
                    )
        return self._model

    def encode(self, texts: list[str]) -> list[list[float]]:
        """Return one normalized embedding vector for every input text."""
        if not texts:
            return []
        embeddings = self._get_model().encode(
            texts,
            convert_to_numpy=True,
            normalize_embeddings=True,
            show_progress_bar=False,
        )
        return embeddings.tolist()


embedding_service = EmbeddingService()
