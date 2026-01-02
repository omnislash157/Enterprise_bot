"""
Modal Serverless GPU Embedder

Deploys BGE-M3 on an A10G GPU. Spins up in ~10s, embeds at 1000+ texts/sec.
Shuts down immediately when done - you only pay for compute time.

Deploy:
    modal deploy memory/modal_embedder.py

Test:
    modal run memory/modal_embedder.py

Cost: ~$0.0003/sec on A10G = ~$0.02 for 10k embeddings
"""

import modal

# Define the Modal app
app = modal.App("cogzy-embedder")

# GPU image with BGE-M3 model
embedder_image = modal.Image.debian_slim(python_version="3.11").pip_install(
    "torch",
    "transformers",
    "sentence-transformers",
    "numpy",
)


@app.cls(
    image=embedder_image,
    gpu="A10G",  # 24GB VRAM, good balance of speed/cost
    timeout=300,  # 5 min max per call
    container_idle_timeout=60,  # Keep warm for 60s between calls
)
class BGEEmbedder:
    """BGE-M3 embedder running on GPU."""

    @modal.enter()
    def load_model(self):
        """Load model when container starts (cached across calls)."""
        from sentence_transformers import SentenceTransformer
        import torch

        self.device = "cuda" if torch.cuda.is_available() else "cpu"
        print(f"Loading BGE-M3 on {self.device}...")

        self.model = SentenceTransformer(
            "BAAI/bge-m3",
            device=self.device,
            trust_remote_code=True,
        )
        # Warmup
        _ = self.model.encode(["warmup"], convert_to_numpy=True)
        print("BGE-M3 loaded and ready")

    @modal.method()
    def embed(self, texts: list[str]) -> list[list[float]]:
        """Embed a batch of texts."""
        if not texts:
            return []

        embeddings = self.model.encode(
            texts,
            batch_size=128,  # GPU can handle large batches
            show_progress_bar=False,
            convert_to_numpy=True,
            normalize_embeddings=True,
        )
        return embeddings.tolist()


# Function endpoint for external calls
@app.function(
    image=embedder_image,
    gpu="A10G",
    timeout=300,
    container_idle_timeout=60,
)
def embed_batch(texts: list[str]) -> list[list[float]]:
    """
    Embed texts using BGE-M3 on GPU.

    This is the function called by ModalProvider.
    """
    from sentence_transformers import SentenceTransformer
    import torch

    device = "cuda" if torch.cuda.is_available() else "cpu"
    model = SentenceTransformer(
        "BAAI/bge-m3",
        device=device,
        trust_remote_code=True,
    )

    embeddings = model.encode(
        texts,
        batch_size=128,
        show_progress_bar=True,
        convert_to_numpy=True,
        normalize_embeddings=True,
    )
    return embeddings.tolist()


# CLI test
@app.local_entrypoint()
def main():
    """Test the embedder."""
    test_texts = [
        "How do I fix an async error in FastAPI?",
        "What's the best way to structure a Python project?",
        "We were debugging the memory engine last night.",
    ]

    print(f"Embedding {len(test_texts)} texts on GPU...")
    embeddings = embed_batch.remote(test_texts)

    print(f"Got {len(embeddings)} embeddings")
    print(f"Dimension: {len(embeddings[0])}")
    print("First embedding (truncated):", embeddings[0][:5])
