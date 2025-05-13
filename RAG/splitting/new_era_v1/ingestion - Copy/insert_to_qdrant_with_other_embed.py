import os
import json
import hashlib
import time
from datetime import datetime
from tqdm import tqdm
import requests

# Import different embedding providers
from openai import OpenAI
from google.generativeai import configure as gemini_configure
from google.generativeai import embed_content
import anthropic
from typing import Optional, List, Dict, Any, Union

# Qdrant client
from qdrant_client import QdrantClient
from qdrant_client.models import PointStruct, VectorParams, Distance

# ==== Constants ====
# Embedding dimensions for different models
DIMENSIONS = {
    "openai:text-embedding-3-small": 1536,
    "openai:text-embedding-3-large": 3072,
    "openai:text-embedding-ada-002": 1536,
    "google:embedding-001": 768,
    "anthropic:claude-3-haiku-20240307": 1024,
    "anthropic:claude-3-sonnet-20240229": 1024,
    "anthropic:claude-3-opus-20240229": 1024, 
    "ollama:nomic-embed-text": 768,
    "ollama:mxbai-embed-large": 1024,
    "ollama:all-minilm": 384
}

# ==== Logger Class ====
class Logger:
    def __init__(self, log_dir="log"):
        os.makedirs(log_dir, exist_ok=True)
        log_filename = datetime.now().strftime("%Y-%m-%d_%H-%M-%S") + "_InsertQdrant.log"
        self.LOG_FILE = os.path.join(log_dir, log_filename)

    def log_info(self, message, status="INFO"):
        timestamp = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
        log_message = f"[{timestamp}] [{status}] {message}\n"
        with open(self.LOG_FILE, "a", encoding="utf-8") as log_file:
            log_file.write(log_message)
        print(log_message.strip())

# ==== Base Embedder Class ====
class BaseEmbedder:
    """Base class for embedders from different providers"""
    
    def __init__(self):
        self.name = "base"
        self.dimension = 0
    
    def embed_text(self, text: str) -> List[float]:
        """Embed the given text into a vector"""
        raise NotImplementedError("This method should be implemented by subclasses")
    
    def get_dimension(self) -> int:
        """Return the dimension of the embedding vector"""
        return self.dimension
    
    def get_provider_name(self) -> str:
        """Return the name of the provider and model"""
        return self.name

# ==== OpenAI Embedder ====
class OpenAIEmbedder(BaseEmbedder):
    def __init__(self, api_key: str, model: str = "text-embedding-3-small"):
        super().__init__()
        self.client = OpenAI(api_key=api_key)
        self.model = model
        self.name = f"openai:{model}"
        self.dimension = DIMENSIONS.get(self.name, 1536)
    
    def embed_text(self, text: str) -> List[float]:
        response = self.client.embeddings.create(
            input=[text],
            model=self.model
        )
        return response.data[0].embedding

# ==== Google Gemini Embedder ====
class GeminiEmbedder(BaseEmbedder):
    def __init__(self, api_key: str, model: str = "embedding-001"):
        super().__init__()
        gemini_configure(api_key=api_key)
        self.model = model
        self.name = f"google:{model}"
        self.dimension = DIMENSIONS.get(self.name, 768)
    
    def embed_text(self, text: str) -> List[float]:
        result = embed_content(
            model=self.model,
            content=text,
            task_type="retrieval_document"
        )
        return result["embedding"]

# ==== Anthropic Claude Embedder ====
class ClaudeEmbedder(BaseEmbedder):
    def __init__(self, api_key: str, model: str = "claude-3-haiku-20240307"):
        super().__init__()
        self.client = anthropic.Anthropic(api_key=api_key)
        self.model = model
        self.name = f"anthropic:{model}"
        self.dimension = DIMENSIONS.get(self.name, 1024)
    
    def embed_text(self, text: str) -> List[float]:
        response = self.client.embeddings.create(
            model=self.model,
            input=text,
            encoding_format="float"
        )
        return response.embedding

# ==== Ollama Local Embedder ====
class OllamaEmbedder(BaseEmbedder):
    def __init__(self, base_url: str = "http://localhost:11434", model: str = "nomic-embed-text"):
        super().__init__()
        self.base_url = base_url
        self.model = model
        self.name = f"ollama:{model}"
        self.dimension = DIMENSIONS.get(self.name, 768)
    
    def embed_text(self, text: str) -> List[float]:
        response = requests.post(
            f"{self.base_url}/api/embeddings",
            headers={"Content-Type": "application/json"},
            json={"model": self.model, "prompt": text}
        )
        if response.status_code != 200:
            raise Exception(f"Ollama API error: {response.text}")
        
        result = response.json()
        return result["embedding"]

# ==== Embedder Factory ====
class EmbedderFactory:
    @staticmethod
    def create_embedder(provider: str, api_key: Optional[str] = None, model: Optional[str] = None, **kwargs) -> BaseEmbedder:
        """Create an embedder based on provider name"""
        if provider == "openai":
            if model is None:
                model = "text-embedding-3-small"
            return OpenAIEmbedder(api_key=api_key, model=model)
        
        elif provider == "google":
            if model is None:
                model = "embedding-001"
            return GeminiEmbedder(api_key=api_key, model=model)
        
        elif provider == "anthropic":
            if model is None:
                model = "claude-3-haiku-20240307"
            return ClaudeEmbedder(api_key=api_key, model=model)
        
        elif provider == "ollama":
            if model is None:
                model = "nomic-embed-text"
            base_url = kwargs.get("base_url", "http://localhost:11434")
            return OllamaEmbedder(base_url=base_url, model=model)
        
        else:
            raise ValueError(f"Unknown provider: {provider}")

# ==== QdrantInserter with Multiple Embedding Models ====
class QdrantInserter:
    def __init__(self,
                 collection_prefix: str,
                 embedding_provider: str = "openai",
                 embedding_model: Optional[str] = None,
                 api_key: Optional[str] = None,
                 host: str = "localhost",
                 port: int = 6333,
                 index_path: str = "database/index.json",
                 **kwargs):
        
        self.logger = Logger()
        self.embedding_provider = embedding_provider
        self.embedding_model = embedding_model
        
        # Create embedder using factory
        self.embedder = EmbedderFactory.create_embedder(
            provider=embedding_provider,
            api_key=api_key,
            model=embedding_model,
            **kwargs
        )
        
        # Generate collection name based on provider and model
        provider_model = self.embedder.get_provider_name()
        self.collection_name = f"{collection_prefix}_{provider_model.replace(':', '_')}"
        
        # Setup Qdrant client
        self.qdrant = QdrantClient(host=host, port=port)
        
        # Get vector dimension from embedder
        self.vector_dimension = self.embedder.get_dimension()
        
        # Set up index path for this specific model
        index_dir = os.path.dirname(index_path)
        index_filename = os.path.basename(index_path)
        index_name, index_ext = os.path.splitext(index_filename)
        self.index_path = os.path.join(index_dir, f"{index_name}_{provider_model.replace(':', '_')}{index_ext}")
        
        # Ensure directory exists
        os.makedirs(os.path.dirname(self.index_path), exist_ok=True)
        
        # Load previously inserted IDs
        self.inserted_ids = self._load_index()
        
        # Ensure collection exists
        self.ensure_collection()
        
        self.logger.log_info(f"Initialized QdrantInserter with {provider_model}, dimension: {self.vector_dimension}")

    def _load_index(self) -> set:
        if os.path.exists(self.index_path):
            try:
                with open(self.index_path, "r", encoding="utf-8") as f:
                    data = json.load(f)
                    self.logger.log_info(f"Loaded index from {self.index_path}, {len(data)} IDs")
                    return set(data)
            except Exception as e:
                self.logger.log_info(f"Failed to read index file: {e}", status="WARNING")
        return set()

    def _save_index(self):
        with open(self.index_path, "w", encoding="utf-8") as f:
            json.dump(sorted(self.inserted_ids), f, indent=2)
        self.logger.log_info(f"Saved index to {self.index_path}, total {len(self.inserted_ids)} IDs")

    def ensure_collection(self):
        if not self.qdrant.collection_exists(self.collection_name):
            self.qdrant.recreate_collection(
                collection_name=self.collection_name,
                vectors_config=VectorParams(size=self.vector_dimension, distance=Distance.COSINE),
            )
            self.logger.log_info(f"Created new collection: {self.collection_name} with dimension {self.vector_dimension}")
        else:
            self.logger.log_info(f"Collection '{self.collection_name}' exists")

    def get_point_id(self, item_id: str) -> int:
        # Deterministic numeric ID from string
        return int(hashlib.sha256(item_id.encode()).hexdigest(), 16) % (10**18)

    def insert_from_json(self, json_path: str, batch_size: int = 10, retry_count: int = 3):
        if not os.path.isfile(json_path):
            self.logger.log_info(f"File not found: {json_path}", status="ERROR")
            return

        # Load the JSON data
        with open(json_path, "r", encoding="utf-8") as f:
            try:
                data = json.load(f)
            except json.JSONDecodeError as e:
                self.logger.log_info(f"Invalid JSON in {json_path}: {e}", status="ERROR")
                return

        # Check if data is in the new format (has "document_metadata" and "chunks")
        is_new_format = "document_metadata" in data and "chunks" in data
        
        if is_new_format:
            self.logger.log_info(f"Detected new JSON format with document metadata")
            items = data["chunks"]
            doc_metadata = data["document_metadata"]
        else:
            self.logger.log_info(f"Detected old JSON format (list of items)")
            items = data
            doc_metadata = {}
        
        total_items = len(items)
        self.logger.log_info(f"Processing {total_items} items with {self.embedding_provider} embedder")
        
        total_embedded = 0
        total_reused = 0
        total_skipped = 0
        total_failed = 0
        modified = False
        
        # Process items in batches
        batch_points = []
        batch_ids = []
        
        for idx, item in enumerate(tqdm(items, desc=f"Processing with {self.embedder.get_provider_name()}")):
            # Get chunk_id or id based on format
            if is_new_format:
                item_id = item.get("chunk_id")
                content_field = "content"
                metadata_field = "metadata"
            else:
                item_id = item.get("id")
                content_field = "text"
                metadata_field = "metadata"

            if not item_id:
                self.logger.log_info(f"SKIP: missing id in item", status="SKIP")
                total_skipped += 1
                continue
                
            if item_id in self.inserted_ids:
                self.logger.log_info(f"SKIP: ID {item_id} already in index", status="SKIP")
                total_skipped += 1
                continue

            text = item.get(content_field, "")
            metadata = item.get(metadata_field, {})
            point_id = self.get_point_id(item_id)
            
            # Check if provider-specific embedding exists
            embedding_key = f"embedding_{self.embedding_provider}"
            provider_embedding_exists = embedding_key in item and item[embedding_key]
            
            try:
                # Check if item already has embedding for this provider
                if provider_embedding_exists:
                    self.logger.log_info(f"REUSE: Using existing {self.embedding_provider} embedding for ID {item_id}")
                    vector = item[embedding_key]
                    total_reused += 1
                else:
                    # Generate new embedding with retry mechanism
                    self.logger.log_info(f"EMBED: Generating new {self.embedding_provider} embedding for ID {item_id}")
                    for attempt in range(retry_count):
                        try:
                            vector = self.embedder.embed_text(text)
                            # Save embedding back to the JSON structure with provider-specific key
                            item[embedding_key] = vector
                            modified = True
                            total_embedded += 1
                            break
                        except Exception as e:
                            if attempt < retry_count - 1:
                                self.logger.log_info(f"Embedding attempt {attempt+1} failed for ID {item_id}: {e}. Retrying...", status="WARN")
                                time.sleep(2)  # Wait before retry
                            else:
                                raise e

                # Prepare payload for Qdrant
                payload = {
                    "item_id": item_id,
                    "text": text,
                    "metadata": metadata,
                    "embedding_provider": self.embedding_provider,
                    "embedding_model": self.embedding_model
                }
                
                if is_new_format:
                    # Add document metadata to the payload
                    payload["document_metadata"] = {
                        "filename": doc_metadata.get("filename", ""),
                        "total_pages": doc_metadata.get("total_pages", 0),
                        "extraction_date": doc_metadata.get("extraction_date", "")
                    }
                
                # Create point and add to batch
                point = PointStruct(id=point_id, vector=vector, payload=payload)
                batch_points.append(point)
                batch_ids.append(item_id)
                
                # If batch is full or this is the last item, upsert to Qdrant
                if len(batch_points) >= batch_size or idx == total_items - 1:
                    try:
                        self.qdrant.upsert(collection_name=self.collection_name, points=batch_points)
                        
                        # Update our index with successfully inserted IDs
                        for inserted_id in batch_ids:
                            self.inserted_ids.add(inserted_id)
                            
                        self.logger.log_info(f"INSERT: Batch of {len(batch_points)} items added to Qdrant")
                        
                        # Clear batch
                        batch_points = []
                        batch_ids = []
                    except Exception as e:
                        self.logger.log_info(f"ERROR upserting batch: {e}", status="ERROR")
                        total_failed += len(batch_points)
            
            except Exception as e:
                self.logger.log_info(f"ERROR processing ID {item_id}: {e}", status="ERROR")
                total_failed += 1
        
        # Save the updated JSON with embeddings back to file if modified
        if modified:
            # Generate a new filename with provider info
            json_dir = os.path.dirname(json_path)
            json_filename = os.path.basename(json_path)
            json_name, json_ext = os.path.splitext(json_filename)
            new_json_path = os.path.join(json_dir, f"{json_name}_{self.embedding_provider}{json_ext}")
            
            self.logger.log_info(f"Saving updated JSON with {self.embedding_provider} embeddings to {new_json_path}")
            with open(new_json_path, "w", encoding="utf-8") as f:
                json.dump(data, f, indent=2)
        
        # Save the index at the end
        self._save_index()
        
        # Log summary
        self.logger.log_info(
            f"Done with {self.embedding_provider}: {total_embedded} newly embedded, {total_reused} reused embeddings, "
            f"{total_skipped} skipped, {total_failed} failed"
        )

# ===== Main =====
if __name__ == "__main__":
    # Configuration
    config = {
        "collection_prefix": "document_vectors",
        "json_file": "database/chunk_result/sample_document_chunk.json",
        "host": "localhost",
        "port": 6333,
        
        # API Keys (replace with your actual keys)
        "openai_api_key": "",
        "google_api_key": "",
        "anthropic_api_key": "",
        
        # Ollama config
        "ollama_base_url": "http://localhost:11434",
        
        # Models to use
        "models": {
            "openai": "text-embedding-3-small",
            "google": "embedding-001",
            "anthropic": "claude-3-haiku-20240307",
            "ollama": "nomic-embed-text"  # or "all-minilm" or "mxbai-embed-large"
        }
    }
    
    # Choose which embedding provider to use
    # Options: "openai", "google", "anthropic", "ollama"
    active_provider = "openai"
    
    # Get API key for the active provider
    api_key = None
    if active_provider == "openai":
        api_key = config["openai_api_key"]
    elif active_provider == "google":
        api_key = config["google_api_key"]
    elif active_provider == "anthropic":
        api_key = config["anthropic_api_key"]
    
    # Additional kwargs for special providers
    kwargs = {}
    if active_provider == "ollama":
        kwargs["base_url"] = config["ollama_base_url"]
    
    # Create inserter for the selected provider
    inserter = QdrantInserter(
        collection_prefix=config["collection_prefix"],
        embedding_provider=active_provider, 
        embedding_model=config["models"][active_provider],
        api_key=api_key,
        host=config["host"],
        port=config["port"],
        **kwargs
    )
    
    # Insert data
    inserter.insert_from_json(config["json_file"])