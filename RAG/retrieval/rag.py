import os
import json
import time
import numpy as np
from typing import List, Dict, Any, Optional, Tuple
from dataclasses import dataclass
from dotenv import load_dotenv
from openai import OpenAI
from qdrant_client import QdrantClient
from qdrant_client.http.models import Filter, FieldCondition, MatchValue, Range
import asyncio
from tqdm import tqdm

# ===== Load Environment Variables =====
load_dotenv()
OPENAI_API_KEY = os.getenv("OPENAI_API_KEY")
QDRANT_HOST = os.getenv("QDRANT_HOST", "localhost")
QDRANT_PORT = int(os.getenv("QDRANT_PORT", "6333"))
COLLECTION_NAME = os.getenv("COLLECTION_NAME", "tomoro_try")

# ===== Configuration =====
@dataclass
class RAGConfig:
    """Configuration for the RAG pipeline"""
    embedding_model: str = "text-embedding-3-small"
    llm_model: str = "gpt-4o-mini"
    temperature: float = 0.0
    top_k: int = 5
    rerank_top_k: int = 10  # We'll retrieve more docs for reranking
    use_reranking: bool = True
    use_rag_fusion: bool = True
    fusion_query_count: int = 3  # Number of query reformulations for RAG Fusion
    similarity_threshold: float = 0.7  # Threshold for filtering by similarity
    query_max_tokens: int = 200  # Max tokens for query generation

# ===== Embedder =====
class Embedder:
    def __init__(self, api_key: str = None, model: str = "text-embedding-3-small"):
        self.client = OpenAI(api_key=api_key)
        self.model = model
        
    def embed_query(self, text: str) -> List[float]:
        """Embeds a text query using OpenAI's embedding model"""
        response = self.client.embeddings.create(
            input=[text],
            model=self.model
        )
        return response.data[0].embedding

# ===== Reranker =====
class Reranker:
    def __init__(self, api_key: str = None):
        self.client = OpenAI(api_key=api_key)
    
    def rerank(self, query: str, documents: List[Dict[str, Any]], top_k: int = 5) -> List[Dict[str, Any]]:
        """Reranks documents based on relevance to query using LLM"""
        # Create reranking prompt
        rerank_prompt = f"""You are an expert document ranker. Rank the following documents based on their relevance to the query:
        
Query: {query}

Rate each document's relevance to the query on a scale of 0-10, where 10 is the highest relevance.
For each document, provide a score and a brief explanation.

Documents:
"""
        
        ranked_docs = []
        
        # Process documents in batches if there are many
        for i, doc in enumerate(documents):
            content = doc.get("text", "")
            # Truncate content if too long
            if len(content) > 1000:
                content = content[:1000] + "..."
                
            rerank_prompt += f"\nDocument {i+1}:\n{content}\n"
        
        # Get rankings from LLM
        response = self.client.chat.completions.create(
            model="gpt-4o-mini",  # Use a faster, cheaper model for reranking
            messages=[
                {"role": "system", "content": "You are an expert document ranker."},
                {"role": "user", "content": rerank_prompt}
            ],
            temperature=0.0
        )
        
        # Parse rankings from response
        ranking_text = response.choices[0].message.content
        
        # Extract scores (this is a simplified parsing logic)
        scores = []
        lines = ranking_text.split("\n")
        for line in lines:
            if "Document" in line and ":" in line and any(str(i) in line for i in range(10)):
                try:
                    # Try to extract score (assuming format like "Document X: 8/10")
                    parts = line.split(":")
                    if len(parts) >= 2:
                        score_part = parts[1].strip()
                        # Extract first number found
                        score = ''.join(c for c in score_part.split()[0] if c.isdigit() or c == '.')
                        if score:
                            scores.append((int(parts[0].split()[1]) - 1, float(score)))
                except Exception:
                    continue
        
        # Sort documents by score
        scores.sort(key=lambda x: x[1], reverse=True)
        
        # Return top k documents
        return [documents[idx] for idx, _ in scores[:top_k]]

# ===== RAG Pipeline =====
class RAGPipeline:
    def __init__(self, config: RAGConfig = None):
        if config is None:
            config = RAGConfig()
        self.config = config
        
        # Initialize components
        self.embedder = Embedder(api_key=OPENAI_API_KEY, model=config.embedding_model)
        self.llm_client = OpenAI(api_key=OPENAI_API_KEY)
        self.qdrant = QdrantClient(host=QDRANT_HOST, port=QDRANT_PORT)
        
        if config.use_reranking:
            self.reranker = Reranker(api_key=OPENAI_API_KEY)
    
    def generate_query_variations(self, user_query: str) -> List[str]:
        """Generate variations of the user query for RAG Fusion"""
        prompt = f"""Generate {self.config.fusion_query_count} different versions of the following user query.
These should maintain the same intent but be phrased differently to capture different semantic aspects.
Return only the reformulated queries, one per line.

Original query: {user_query}
"""
        
        response = self.llm_client.chat.completions.create(
            model=self.config.llm_model,
            messages=[
                {"role": "system", "content": "You are a helpful query reformulation assistant."},
                {"role": "user", "content": prompt}
            ],
            temperature=0.7,
            max_tokens=self.config.query_max_tokens
        )
        
        # Parse the output to get query variations
        variations = response.choices[0].message.content.strip().split('\n')
        # Ensure we have the original query too
        variations = [user_query] + variations
        # Remove any numbering that might be in the response
        variations = [v.strip().lstrip('123456789.').strip() for v in variations]
        # Remove duplicates
        variations = list(dict.fromkeys(variations))
        
        return variations[:self.config.fusion_query_count]
    
    def reciprocal_rank_fusion(self, results_lists: List[List[Dict]], k: int = 60) -> List[Dict]:
        """Combine multiple search results using Reciprocal Rank Fusion.
        
        Args:
            results_lists: List of search results lists
            k: Constant to prevent division by zero and reduce impact of high rankings
            
        Returns:
            Combined and reordered results list
        """
        # Track all documents and their scores
        doc_scores = {}
        
        for results in results_lists:
            # Process each result list
            for rank, doc in enumerate(results):
                doc_id = doc.get("item_id", "")
                if not doc_id:
                    continue
                
                # RRF formula: 1 / (rank + k)
                score = 1.0 / (rank + k)
                
                if doc_id in doc_scores:
                    doc_scores[doc_id]["score"] += score
                else:
                    doc_scores[doc_id] = {"score": score, "doc": doc}
        
        # Sort documents by score
        sorted_docs = sorted(doc_scores.values(), key=lambda x: x["score"], reverse=True)
        
        # Return just the documents
        return [item["doc"] for item in sorted_docs]
    
    def retrieve(self, query: str) -> List[Dict[str, Any]]:
        """Retrieve relevant documents for the given query"""
        if self.config.use_rag_fusion:
            # Generate query variations
            query_variations = self.generate_query_variations(query)
            print(f"Query variations: {query_variations}")
            
            # Get results for each query variation
            all_results = []
            for q in query_variations:
                # Embed query
                query_embedding = self.embedder.embed_query(q)
                
                # Search Qdrant
                search_result = self.qdrant.search(
                    collection_name=COLLECTION_NAME,
                    query_vector=query_embedding,
                    limit=self.config.rerank_top_k if self.config.use_reranking else self.config.top_k,
                    with_payload=True,
                    score_threshold=self.config.similarity_threshold
                )
                
                # Convert to a standardized format
                results = []
                for hit in search_result:
                    doc = {
                        "item_id": hit.payload.get("item_id", ""),
                        "text": hit.payload.get("text", ""),
                        "score": hit.score,
                        "metadata": hit.payload.get("metadata", {})
                    }
                    
                    # Add document metadata if available
                    if "document_metadata" in hit.payload:
                        doc["document_metadata"] = hit.payload["document_metadata"]
                        
                    results.append(doc)
                
                all_results.append(results)
            
            # Combine results using RRF
            combined_results = self.reciprocal_rank_fusion(all_results)
            
            # Apply reranking if enabled
            if self.config.use_reranking:
                return self.reranker.rerank(query, combined_results, self.config.top_k)
            else:
                return combined_results[:self.config.top_k]
        else:
            # Standard retrieval process
            query_embedding = self.embedder.embed_query(query)
            
            # Search Qdrant
            search_result = self.qdrant.search(
                collection_name=COLLECTION_NAME,
                query_vector=query_embedding,
                limit=self.config.rerank_top_k if self.config.use_reranking else self.config.top_k,
                with_payload=True,
                score_threshold=self.config.similarity_threshold
            )
            
            # Convert to a standardized format
            results = []
            for hit in search_result:
                doc = {
                    "item_id": hit.payload.get("item_id", ""),
                    "text": hit.payload.get("text", ""),
                    "score": hit.score,
                    "metadata": hit.payload.get("metadata", {})
                }
                
                # Add document metadata if available
                if "document_metadata" in hit.payload:
                    doc["document_metadata"] = hit.payload["document_metadata"]
                    
                results.append(doc)
            
            # Apply reranking if enabled
            if self.config.use_reranking:
                return self.reranker.rerank(query, results, self.config.top_k)
            else:
                return results
    
    def format_context(self, documents: List[Dict]) -> str:
        """Format retrieved documents into context for the LLM"""
        context = ""
        
        for i, doc in enumerate(documents):
            # Add document content
            text = doc.get("text", "")
            source = ""
            
            # Get source information
            metadata = doc.get("metadata", {})
            doc_metadata = doc.get("document_metadata", {})
            
            if doc_metadata:
                filename = doc_metadata.get("filename", "")
                if filename:
                    source = f"Filename: {filename}"
                    
                    # Add page number if available
                    if "page" in metadata:
                        source += f", Page: {metadata['page']}"
                    elif "pages" in metadata and metadata["pages"]:
                        source += f", Pages: {', '.join(map(str, metadata['pages']))}"
            
            # Format the document
            if source:
                context += f"\n\n[Document {i+1}] Source: {source}\n{text}\n"
            else:
                context += f"\n\n[Document {i+1}]\n{text}\n"
        
        return context
    
    def answer_question(self, user_query: str) -> Dict[str, Any]:
        """Full RAG pipeline to answer user query"""
        start_time = time.time()
        
        # Retrieve relevant documents
        retrieved_docs = self.retrieve(user_query)
        
        # Format context
        context = self.format_context(retrieved_docs)
        
        # Generate answer using LLM
        prompt = f"""Answer the following question based ONLY on the provided context. If the answer cannot be determined from the context, say "I don't have enough information to answer this question."

Context:
{context}

Question: {user_query}

Answer:"""
        
        response = self.llm_client.chat.completions.create(
            model=self.config.llm_model,
            messages=[
                {"role": "system", "content": "You are a helpful assistant that answers questions based on provided context."},
                {"role": "user", "content": prompt}
            ],
            temperature=self.config.temperature
        )
        
        # Format sources for citation
        sources = []
        for doc in retrieved_docs:
            source_info = {}
            
            # Get metadata
            metadata = doc.get("metadata", {})
            doc_metadata = doc.get("document_metadata", {})
            
            if doc_metadata:
                source_info["filename"] = doc_metadata.get("filename", "")
                
                # Add page info
                if "page" in metadata:
                    source_info["page"] = metadata["page"]
                elif "pages" in metadata and metadata["pages"]:
                    source_info["pages"] = metadata["pages"]
            
            # Add to sources if we have information
            if source_info:
                sources.append(source_info)
        
        end_time = time.time()
        
        return {
            "answer": response.choices[0].message.content,
            "sources": sources,
            "retrieved_count": len(retrieved_docs),
            "processing_time": round(end_time - start_time, 2)
        }

# ===== Command Line Interface =====
def main():
    print("📚 Tomoro RAG System 📚")
    print("Connecting to Qdrant...")
    
    # Create pipeline with selected strategies
    config = RAGConfig(
        use_reranking=True,
        use_rag_fusion=True,
        fusion_query_count=3,
        top_k=5,
        rerank_top_k=10,
        llm_model="gpt-4o-mini",  # Can be changed to gpt-4o-mini for faster responses
    )
    
    rag = RAGPipeline(config)
    
    # Check if Qdrant collection exists
    try:
        collections = rag.qdrant.get_collections().collections
        collection_names = [c.name for c in collections]
        
        if COLLECTION_NAME not in collection_names:
            print(f"⚠️ Collection '{COLLECTION_NAME}' not found in Qdrant.")
            print(f"Available collections: {', '.join(collection_names)}")
            return
        
        # Get collection info
        collection_info = rag.qdrant.get_collection(COLLECTION_NAME)
        points_count = collection_info.points_count
        
        print(f"✅ Connected to Qdrant collection '{COLLECTION_NAME}' with {points_count} points.")
    except Exception as e:
        print(f"❌ Error connecting to Qdrant: {e}")
        return
    
    print("\nEnter your questions below (type 'exit' to quit):")
    
    while True:
        user_query = input("\n🔍 Question: ")
        
        if user_query.lower() in ['exit', 'quit']:
            print("Goodbye! 👋")
            break
        
        if not user_query.strip():
            continue
        
        try:
            print("Searching for relevant information...")
            result = rag.answer_question(user_query)
            
            print("\n📝 Answer:")
            print(result["answer"])
            
            print(f"\n📊 Retrieved {result['retrieved_count']} relevant documents in {result['processing_time']}s")
            
            if result["sources"]:
                print("\n📎 Sources:")
                for i, source in enumerate(result["sources"]):
                    source_text = f"  {i+1}. {source.get('filename', '')}"
                    if "page" in source:
                        source_text += f", Page {source['page']}"
                    elif "pages" in source:
                        source_text += f", Pages {', '.join(map(str, source['pages']))}"
                    print(source_text)
        except Exception as e:
            print(f"❌ Error: {e}")

if __name__ == "__main__":
    main()