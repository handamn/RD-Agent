## How to use
## uvicorn rag_api:app --host 0.0.0.0 --port 8000 --reload

import os
import json
import time
import math
import logging
import argparse
import numpy as np
import re
from typing import List, Dict, Any, Tuple, Optional, Union

from dotenv import load_dotenv
from rich.console import Console
from rich.markdown import Markdown
from openai import OpenAI
from qdrant_client import QdrantClient
from qdrant_client.http.models import Filter, FieldCondition, MatchText, MatchValue, Range
from rank_bm25 import BM25Okapi
import nltk
from nltk.tokenize import word_tokenize
try:
    nltk.data.find('tokenizers/punkt')
except LookupError:
    nltk.download('punkt')

# Setup logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    handlers=[logging.FileHandler("rag.log"), logging.StreamHandler()]
)
logger = logging.getLogger("RAG")

# Rich console for pretty output
console = Console()

class EmbeddingGenerator:
    """Class to generate embeddings using OpenAI"""
    
    def __init__(self, model="text-embedding-3-small"):
        """Initialize the embedding generator with OpenAI client"""
        load_dotenv()
        self.client = OpenAI(api_key=os.getenv("OPENAI_API_KEY"))
        self.model = model
    
    def get_embedding(self, text: str) -> List[float]:
        """Generate embedding for text"""
        try:
            response = self.client.embeddings.create(
                input=[text], 
                model=self.model
            )
            return response.data[0].embedding
        except Exception as e:
            logger.error(f"Error generating embedding: {e}")
            raise

class TextChunker:
    """Class to handle text chunking with various strategies"""
    
    def __init__(self, 
                chunk_size: int = 1000, 
                chunk_overlap: int = 200, 
                strategy: str = "sliding_window"):
        """Initialize the text chunker"""
        self.chunk_size = chunk_size
        self.chunk_overlap = chunk_overlap
        self.strategy = strategy
    
    def chunk_text(self, text: str, metadata: Dict = None) -> List[Dict]:
        """Chunk text based on selected strategy"""
        if self.strategy == "sliding_window":
            return self._sliding_window_chunking(text, metadata)
        elif self.strategy == "paragraph":
            return self._paragraph_chunking(text, metadata)
        else:
            logger.warning(f"Unknown chunking strategy: {self.strategy}. Falling back to sliding window.")
            return self._sliding_window_chunking(text, metadata)
    
    def _sliding_window_chunking(self, text: str, metadata: Dict = None) -> List[Dict]:
        """Chunk text using sliding window with overlap"""
        chunks = []
        
        # Handle very short texts
        if len(text) <= self.chunk_size:
            return [{"text": text, "metadata": metadata or {}}]
        
        start = 0
        while start < len(text):
            # Find the end of the current chunk
            end = start + self.chunk_size
            
            # If we're not at the end of the text, try to find a good break point
            if end < len(text):
                # Look for a period, question mark, or exclamation point followed by space or newline
                # within the last 20% of the chunk
                search_start = end - int(0.2 * self.chunk_size)
                search_text = text[search_start:end]
                
                # Look for sentence endings
                sentence_endings = [m.start() for m in re.finditer(r'[.!?]\s', search_text)]
                if sentence_endings:
                    # Use the last sentence ending found
                    last_period = sentence_endings[-1]
                    end = search_start + last_period + 2  # +2 to include the period and space
            
            # Create the chunk
            chunk_text = text[start:end].strip()
            if chunk_text:  # Only add non-empty chunks
                chunk_metadata = metadata.copy() if metadata else {}
                chunk_metadata["chunk_index"] = len(chunks)
                chunks.append({"text": chunk_text, "metadata": chunk_metadata})
            
            # Move the start position for the next chunk
            start = end - self.chunk_overlap
            
            # Ensure we're making progress
            if start <= 0:
                start = end
        
        return chunks
    
    def _paragraph_chunking(self, text: str, metadata: Dict = None) -> List[Dict]:
        """Chunk text by paragraphs, combining short paragraphs if needed"""
        # Split text into paragraphs
        paragraphs = [p.strip() for p in text.split("\n\n") if p.strip()]
        
        chunks = []
        current_chunk = ""
        current_size = 0
        
        for para in paragraphs:
            para_size = len(para)
            
            # If adding this paragraph would exceed chunk size and we already have content
            if current_size + para_size > self.chunk_size and current_chunk:
                # Store the current chunk
                chunk_metadata = metadata.copy() if metadata else {}
                chunk_metadata["chunk_index"] = len(chunks)
                chunks.append({"text": current_chunk.strip(), "metadata": chunk_metadata})
                
                # Start a new chunk
                current_chunk = para
                current_size = para_size
            else:
                # Add to the current chunk
                if current_chunk:
                    current_chunk += "\n\n" + para
                else:
                    current_chunk = para
                current_size += para_size
        
        # Don't forget the last chunk
        if current_chunk:
            chunk_metadata = metadata.copy() if metadata else {}
            chunk_metadata["chunk_index"] = len(chunks)
            chunks.append({"text": current_chunk.strip(), "metadata": chunk_metadata})
        
        return chunks

class QdrantRetriever:
    """Class to retrieve documents from Qdrant with hybrid search support"""
    
    def __init__(self, collection_name: str, host="localhost", port=6333):
        """Initialize connection to Qdrant"""
        self.client = QdrantClient(host=host, port=port)
        self.collection_name = collection_name
        logger.info(f"Connected to Qdrant collection: {collection_name}")
    
    def retrieve(self, 
                 query_vector: List[float], 
                 limit: int = 5, 
                 filter_params: Optional[Dict] = None) -> List[Dict]:
        """Retrieve documents from Qdrant based on query vector"""
        filter_condition = self._create_filter(filter_params)
        
        try:
            results = self.client.search(
                collection_name=self.collection_name,
                query_vector=query_vector,
                limit=limit,
                query_filter=filter_condition
            )
            
            return [
                {
                    "id": hit.id,
                    "score": hit.score,
                    "text": hit.payload.get("text", ""),
                    "metadata": hit.payload.get("metadata", {}),
                    "document_metadata": hit.payload.get("document_metadata", {})
                }
                for hit in results
            ]
        except Exception as e:
            logger.error(f"Error retrieving from Qdrant: {e}")
            return []
    
    def keyword_search(self, 
                      query: str, 
                      limit: int = 5, 
                      filter_params: Optional[Dict] = None,
                      fields: List[str] = ["text"]) -> List[Dict]:
        """Perform keyword search using Qdrant's built-in full-text search"""
        filter_condition = self._create_filter(filter_params)
        
        try:
            # Add text match conditions
            text_conditions = []
            for field in fields:
                text_conditions.append(
                    FieldCondition(
                        key=field,
                        match=MatchText(text=query)
                    )
                )
            
            # Combine with other filters if any
            if filter_condition and filter_condition.must:
                filter_condition.must.extend(text_conditions)
            else:
                filter_condition = Filter(must=text_conditions)
            
            # Perform search
            results = self.client.scroll(
                collection_name=self.collection_name,
                limit=limit,
                scroll_filter=filter_condition
            )
            
            return [
                {
                    "id": hit.id,
                    "score": 0.5,  # Default score for keyword search
                    "text": hit.payload.get("text", ""),
                    "metadata": hit.payload.get("metadata", {}),
                    "document_metadata": hit.payload.get("document_metadata", {})
                }
                for hit in results[0]  # results[0] contains the points
            ]
        except Exception as e:
            logger.error(f"Error performing keyword search: {e}")
            return []
    
    def hybrid_search(self,
                      query: str,
                      query_vector: List[float],
                      limit: int = 10,
                      filter_params: Optional[Dict] = None,
                      vector_weight: float = 0.7) -> List[Dict]:
        """Perform hybrid search combining vector search and keyword search"""
        # Get more results than needed for proper fusion
        expanded_limit = min(limit * 3, 30)  # Get 3x results but cap at 30
        
        # Get results from both methods
        vector_results = self.retrieve(query_vector, limit=expanded_limit, filter_params=filter_params)
        keyword_results = self.keyword_search(query, limit=expanded_limit, filter_params=filter_params)
        
        # Create a combined result set
        combined_results = {}
        
        # Process vector results
        for doc in vector_results:
            doc_id = doc["id"]
            combined_results[doc_id] = {
                **doc,
                "vector_score": doc["score"],
                "keyword_score": 0.0,
                "combined_score": doc["score"] * vector_weight
            }
        
        # Process keyword results
        for doc in keyword_results:
            doc_id = doc["id"]
            keyword_score = 0.5  # Default score for keyword matches
            
            if doc_id in combined_results:
                # Update existing entry
                combined_results[doc_id]["keyword_score"] = keyword_score
                combined_results[doc_id]["combined_score"] += keyword_score * (1 - vector_weight)
            else:
                # Add new entry
                combined_results[doc_id] = {
                    **doc,
                    "vector_score": 0.0,
                    "keyword_score": keyword_score,
                    "combined_score": keyword_score * (1 - vector_weight)
                }
        
        # Convert to list and sort by combined score
        result_list = list(combined_results.values())
        result_list.sort(key=lambda x: x["combined_score"], reverse=True)
        
        # Update the score field to be the combined score
        for doc in result_list:
            doc["score"] = doc["combined_score"]
        
        return result_list[:limit]
    
    def _create_filter(self, filter_params: Optional[Dict]) -> Optional[Filter]:
        """Create a Qdrant filter from parameters"""
        if not filter_params:
            return None
        
        conditions = []
        for field, value in filter_params.items():
            conditions.append(FieldCondition(key=field, match=MatchValue(value=value)))
        
        return Filter(must=conditions) if conditions else None

class QueryExpander:
    """Class to expand original query into multiple search queries"""
    
    def __init__(self):
        """Initialize the query expander with OpenAI client"""
        load_dotenv()
        self.client = OpenAI(api_key=os.getenv("OPENAI_API_KEY"))
    
    def expand_query(self, original_query: str) -> List[str]:
        """Expand the original query into multiple search queries"""
        try:
            response = self.client.chat.completions.create(
                model="gpt-4o-mini",
                messages=[
                    {"role": "system", "content": """
                    You are a query expansion specialist for a financial and investment document retrieval system.
                    Your job is to take an original search query and generate 2-3 alternative search queries that 
                    help capture different relevant aspects or terminologies. Consider financial terms, 
                    regulatory aspects, and investment concepts in your expansions.
                    Return only the expanded queries as a numbered list, nothing else.
                    """},
                    {"role": "user", "content": f"Original query: {original_query}"}
                ],
                temperature=0.3,
                max_tokens=200
            )
            
            # Parse the response to extract queries
            expanded_text = response.choices[0].message.content.strip()
            # Extract individual queries, removing numbering
            expanded_queries = []
            for line in expanded_text.split('\n'):
                if line.strip():
                    # Remove numbering like "1. " or "1) "
                    cleaned_line = line.strip()
                    if cleaned_line[0].isdigit() and cleaned_line[1:3] in ['. ', ') ']:
                        cleaned_line = cleaned_line[3:]
                    expanded_queries.append(cleaned_line)
            
            # Always include the original query
            if original_query not in expanded_queries:
                expanded_queries.insert(0, original_query)
                
            return expanded_queries
        except Exception as e:
            logger.error(f"Error expanding query: {e}")
            # Return original query if expansion fails
            return [original_query]

class BM25Retriever:
    """Class to retrieve documents using BM25 algorithm"""
    
    def __init__(self):
        """Initialize the BM25 retriever"""
        self.corpus = []
        self.doc_info = []
        self.tokenized_corpus = []
        self.bm25 = None
        self.initialized = False
    
    def initialize(self, documents: List[Dict]):
        """Initialize the BM25 model with documents"""
        self.corpus = [doc["text"] for doc in documents]
        self.doc_info = documents
        
        # Tokenize corpus
        self.tokenized_corpus = [word_tokenize(doc.lower()) for doc in self.corpus]
        
        # Create BM25 model
        self.bm25 = BM25Okapi(self.tokenized_corpus)
        self.initialized = True
        logger.info(f"BM25 initialized with {len(self.corpus)} documents")
    
    def retrieve(self, query: str, limit: int = 5) -> List[Dict]:
        """Retrieve documents based on BM25 scoring"""
        if not self.initialized:
            logger.warning("BM25 retriever not initialized")
            return []
        
        try:
            # Tokenize query
            tokenized_query = word_tokenize(query.lower())
            
            # Get BM25 scores
            scores = self.bm25.get_scores(tokenized_query)
            
            # Get top documents
            top_indices = np.argsort(scores)[::-1][:limit]
            
            # Create result list
            results = []
            for idx in top_indices:
                if scores[idx] > 0:  # Only include documents with positive scores
                    doc = self.doc_info[idx].copy()
                    doc["score"] = float(scores[idx])  # Convert numpy.float to Python float
                    results.append(doc)
            
            return results
        except Exception as e:
            logger.error(f"Error retrieving with BM25: {e}")
            return []

class RankFusion:
    """Class to implement Reciprocal Rank Fusion for combining results"""
    
    def __init__(self, k: float = 60.0):
        """Initialize rank fusion with constant k"""
        self.k = k
    
    def fuse(self, result_lists: List[List[Dict]], weights: List[float] = None) -> List[Dict]:
        """Fuse multiple result lists using Reciprocal Rank Fusion"""
        if not result_lists:
            return []
        
        # Use equal weights if not provided
        if weights is None:
            weights = [1.0] * len(result_lists)
        
        # Normalize weights to sum to 1
        total_weight = sum(weights)
        if total_weight > 0:
            weights = [w / total_weight for w in weights]
        else:
            weights = [1.0 / len(weights)] * len(weights)
        
        # Calculate RRF scores
        fused_scores = {}
        
        for i, results in enumerate(result_lists):
            for rank, doc in enumerate(results):
                doc_id = doc["id"]
                
                # RRF formula: 1 / (k + rank)
                rrf_score = weights[i] * (1.0 / (self.k + rank))
                
                if doc_id in fused_scores:
                    fused_scores[doc_id]["score"] += rrf_score
                    # Keep the doc info from the first occurrence
                else:
                    doc_copy = doc.copy()
                    doc_copy["score"] = rrf_score
                    fused_scores[doc_id] = doc_copy
        
        # Convert to list and sort by score
        fused_list = list(fused_scores.values())
        fused_list.sort(key=lambda x: x["score"], reverse=True)
        
        return fused_list

class Reranker:
    """Class to rerank retrieved documents"""
    
    def __init__(self):
        """Initialize the reranker with OpenAI client"""
        load_dotenv()
        self.client = OpenAI(api_key=os.getenv("OPENAI_API_KEY"))
    
    def rerank(self, query: str, documents: List[Dict]) -> List[Dict]:
        """Rerank documents based on their relevance to the query"""
        if not documents:
            return []
        
        # Prepare documents for scoring
        doc_texts = [doc["text"] for doc in documents]
        
        try:
            # Use OpenAI to score relevance
            response = self.client.chat.completions.create(
                model="gpt-4o-mini",
                messages=[
                    {"role": "system", "content": """
                    You are a relevance scoring system. You will be given a query and a list of document 
                    passages. Your task is to score each passage's relevance to the query on a scale of 0-100,
                    where 100 is most relevant and 0 is completely irrelevant.
                    
                    Return only a JSON array of scores, nothing else. For example: {"scores": [95, 80, 45, 20]}
                    """},
                    {"role": "user", "content": f"Query: {query}\n\nDocuments:\n" + 
                     "\n---\n".join([f"Document {i+1}: {doc}" for i, doc in enumerate(doc_texts)])}
                ],
                response_format={"type": "json_object"},
                temperature=0.1,
                max_tokens=300
            )
            
            # Extract scores
            result = json.loads(response.choices[0].message.content)
            scores = result.get("scores", [])
            
            # If scores don't match documents length, use original scores
            if len(scores) != len(documents):
                logger.warning(f"Reranking returned {len(scores)} scores for {len(documents)} documents")
                return documents
            
            # Create new list with updated scores
            reranked_docs = []
            for i, doc in enumerate(documents):
                doc_copy = doc.copy()
                doc_copy["original_score"] = doc["score"]
                doc_copy["score"] = scores[i] / 100.0  # Normalize to 0-1
                reranked_docs.append(doc_copy)
            
            # Sort by new score
            reranked_docs.sort(key=lambda x: x["score"], reverse=True)
            return reranked_docs
            
        except Exception as e:
            logger.error(f"Error reranking documents: {e}")
            # Return original documents if reranking fails
            return documents

class SelfEvaluator:
    """Class to evaluate the quality of RAG responses"""
    
    def __init__(self):
        """Initialize the self-evaluator with OpenAI client"""
        load_dotenv()
        self.client = OpenAI(api_key=os.getenv("OPENAI_API_KEY"))
    
    def evaluate_response(self, query: str, response: str, contexts: List[str]) -> Dict:
        """Evaluate the response quality and factuality"""
        try:
            eval_response = self.client.chat.completions.create(
                model="gpt-4o-mini",
                messages=[
                    {"role": "system", "content": """
                    You are an expert evaluator for retrieval-augmented generation systems.
                    Your task is to evaluate the quality of an answer generated from retrieved contexts.
                    For each evaluation, provide scores on these dimensions:
                    
                    1. Relevance (0-10): How well the answer addresses the query
                    2. Factual accuracy (0-10): How accurately the answer represents information from the contexts
                    3. Completeness (0-10): How comprehensively the answer covers relevant information
                    4. Hallucination (0-10): The degree to which the answer contains information NOT in the contexts (0=no hallucination, 10=severe hallucination)
                    
                    Return your evaluation as a JSON object with these scores and a brief justification for each.
                    """},
                    {"role": "user", "content": 
                     f"Query: {query}\n\nAnswer: {response}\n\nContexts:\n" + 
                     "\n---\n".join([f"Context {i+1}: {ctx}" for i, ctx in enumerate(contexts)])
                    }
                ],
                response_format={"type": "json_object"},
                temperature=0.1,
                max_tokens=500
            )
            
            result = json.loads(eval_response.choices[0].message.content)
            return result
            
        except Exception as e:
            logger.error(f"Error evaluating response: {e}")
            return {
                "relevance": -1,
                "factual_accuracy": -1,
                "completeness": -1,
                "hallucination": -1,
                "error": str(e)
            }

class ImprovedRAGSystem:
    """Enhanced RAG system with multiple retrieval techniques"""
    
    def __init__(self, collection_name: str, host="localhost", port=6333):
        """Initialize enhanced RAG system components"""
        self.embedding_generator = EmbeddingGenerator()
        self.retriever = QdrantRetriever(collection_name, host, port)
        self.query_expander = QueryExpander()
        self.reranker = Reranker()
        self.rank_fusion = RankFusion(k=60.0)
        self.self_evaluator = SelfEvaluator()
        self.client = OpenAI(api_key=os.getenv("OPENAI_API_KEY"))
        # BM25 retriever will be initialized when needed with the document set
        self.bm25_retriever = BM25Retriever()
        logger.info("Enhanced RAG system initialized")
    
    def process_query(self, 
                      query: str, 
                      use_query_expansion: bool = True, 
                      use_hybrid_search: bool = True,
                      use_reranking: bool = True, 
                      limit: int = 5,
                      filter_params: Optional[Dict] = None,
                      evaluate_response: bool = False) -> Dict:
        """Process a query through the enhanced RAG pipeline"""
        start_time = time.time()
        logger.info(f"Processing query: {query}")
        
        # Step 1: Query Expansion (optional)
        if use_query_expansion:
            expanded_queries = self.query_expander.expand_query(query)
            logger.info(f"Expanded queries: {expanded_queries}")
        else:
            expanded_queries = [query]
        
        # Step 2: Retrieve documents using multiple methods
        all_retrieval_results = []
        
        # Process each expanded query
        for q in expanded_queries:
            # Generate embedding for vector search
            query_embedding = self.embedding_generator.get_embedding(q)
            
            if use_hybrid_search:
                # Hybrid search (vector + keyword)
                docs = self.retriever.hybrid_search(
                    query=q,
                    query_vector=query_embedding,
                    limit=limit * 2,  # Get more results for fusion
                    filter_params=filter_params
                )
                all_retrieval_results.append(docs)
            else:
                # Pure vector search
                docs = self.retriever.retrieve(
                    query_vector=query_embedding,
                    limit=limit * 2,
                    filter_params=filter_params
                )
                all_retrieval_results.append(docs)
        
        # Fuse results from all queries
        fused_results = self.rank_fusion.fuse(all_retrieval_results)
        
        # Step 3: Reranking (optional)
        if use_reranking and fused_results:
            reranked_docs = self.reranker.rerank(query, fused_results)
            # Limit to top results after reranking
            retrieved_docs = reranked_docs[:limit]
        else:
            # Just take top results from fusion
            retrieved_docs = fused_results[:limit]
        
        # Step 4: Generate response
        context = self._prepare_context(retrieved_docs)
        answer = self._generate_answer(query, context, retrieved_docs)
        
        # Step 5: Self-evaluation (optional)
        evaluation = None
        if evaluate_response:
            context_texts = [doc["text"] for doc in retrieved_docs]
            evaluation = self.self_evaluator.evaluate_response(query, answer, context_texts)
        
        execution_time = time.time() - start_time
        logger.info(f"Query processed in {execution_time:.2f} seconds")
        
        # Return complete result
        result = {
            "query": query,
            "answer": answer,
            "retrieved_documents": retrieved_docs,
            "execution_time": execution_time
        }
        
        if evaluation:
            result["evaluation"] = evaluation
            
        return result
    
    def _prepare_context(self, documents: List[Dict]) -> str:
        """Prepare context string from retrieved documents"""
        context_parts = []
        
        for i, doc in enumerate(documents):
            # Get document metadata
            doc_metadata = doc.get("document_metadata", {})
            doc_filename = doc_metadata.get("filename", "Unknown document")
            
            # Get chunk metadata
            metadata = doc.get("metadata", {})
            page_info = metadata.get("page", metadata.get("pages", ["Unknown"]))
            if isinstance(page_info, list):
                page_info = ", ".join(map(str, page_info))
            
            # Prepare context entry
            context_parts.append(
                f"[Document: {doc_filename}, Page(s): {page_info}]\n{doc['text']}\n"
            )
        
        return "\n---\n".join(context_parts)
    
    def _generate_answer(self, query: str, context: str, retrieved_docs: List[Dict]) -> str:
        """Generate an answer using retrieved context"""
        try:
            # Source documents for citation
            sources = []
            for doc in retrieved_docs:
                doc_metadata = doc.get("document_metadata", {})
                metadata = doc.get("metadata", {})
                filename = doc_metadata.get("filename", "Unknown document")
                
                page_info = metadata.get("page", metadata.get("pages", ["Unknown"]))
                if isinstance(page_info, list):
                    page_info = ", ".join(map(str, page_info))
                
                sources.append(f"{filename} (Hal. {page_info})")
            
            # Generate answer
            response = self.client.chat.completions.create(
                model="gpt-4o-mini",
                messages=[
                    {"role": "system", "content": """
                    Anda adalah asisten yang membantu menjawab pertanyaan berdasarkan konteks dokumen yang diberikan.
                    Gunakan hanya informasi yang tersedia dalam konteks untuk menjawab pertanyaan.
                    Jika informasi tidak tersedia dalam konteks, katakan bahwa Anda tidak dapat menemukan informasinya.
                    Berikan jawaban yang komprehensif dan faktual. Saat menjawab, gunakan bahasa Indonesia yang baik dan benar.
                    
                    Setiap jawaban harus disertai dengan sumber informasi di akhir jawaban.
                    """},
                    {"role": "user", "content": f"Konteks:\n{context}\n\nPertanyaan: {query}"}
                ],
                temperature=0.3,
                max_tokens=1000
            )
            
            answer = response.choices[0].message.content.strip()
            
            # Add sources if not already included
            if "Sumber:" not in answer:
                unique_sources = list(set(sources))
                sources_text = "\n".join([f"- {src}" for src in unique_sources])
                answer += f"\n\nSumber:\n{sources_text}"
            
            return answer
            
        except Exception as e:
            logger.error(f"Error generating answer: {e}")
            return f"Maaf, terjadi kesalahan dalam menghasilkan jawaban: {str(e)}"

def chat_loop(rag_system):
    """Interactive chat loop with enhanced settings"""
    console.print("\n[bold green]Enhanced RAG Chat System[/bold green]")
    console.print("Ketik 'exit' untuk keluar, 'settings' untuk mengubah pengaturan RAG\n")
    
    # Default settings
    settings = {
        "use_query_expansion": True,
        "use_hybrid_search": True,
        "use_reranking": True,
        "evaluate_response": False,
        "limit": 5,
        "filter_params": None
    }
    
    while True:
        try:
            # Get user query
            query = input("\n[Anda]: ")
            
            if query.lower() == 'exit':
                break
                
            elif query.lower() == 'settings':
                console.print("\n[bold]Pengaturan RAG:[/bold]")
                settings["use_query_expansion"] = console.input("Gunakan query expansion? (y/n): ").lower() == 'y'
                settings["use_hybrid_search"] = console.input("Gunakan hybrid search? (y/n): ").lower() == 'y'
                settings["use_reranking"] = console.input("Gunakan reranking? (y/n): ").lower() == 'y'
                settings["evaluate_response"] = console.input("Evaluasi jawaban? (y/n): ").lower() == 'y'
                settings["limit"] = int(console.input("Jumlah dokumen untuk diambil: "))
                
                # Filter settings
                use_filter = console.input("Gunakan filter dokumen? (y/n): ").lower() == 'y'
                if use_filter:
                    filter_field = console.input("Nama field filter (contoh: document_metadata.filename): ")
                    filter_value = console.input("Nilai filter: ")
                    settings["filter_params"] = {filter_field: filter_value}
                else:
                    settings["filter_params"] = None
                
                console.print("[green]Pengaturan berhasil diubah![/green]")
                continue
            
            # Process query
            result = rag_system.process_query(
                query=query,
                use_query_expansion=settings["use_query_expansion"],
                use_hybrid_search=settings["use_hybrid_search"],
                use_reranking=settings["use_reranking"],
                limit=settings["limit"],
                filter_params=settings["filter_params"],
                evaluate_response=settings["evaluate_response"]
            )
            
            # Display answer
            console.print("\n[bold cyan][RAG]:[/bold cyan]")
            console.print(Markdown(result["answer"]))
            
            # Display evaluation if available
            if settings["evaluate_response"] and "evaluation" in result:
                eval_data = result["evaluation"]
                console.print("\n[bold yellow]Evaluasi Jawaban:[/bold yellow]")
                console.print(f"Relevansi: {eval_data.get('relevance', 'N/A')}/10")
                console.print(f"Akurasi Faktual: {eval_data.get('factual_accuracy', 'N/A')}/10")
                console.print(f"Kelengkapan: {eval_data.get('completeness', 'N/A')}/10")
                console.print(f"Halusinasi: {eval_data.get('hallucination', 'N/A')}/10")
                if "justification" in eval_data:
                    console.print(f"Justifikasi: {eval_data['justification']}")
            
            # Option to see retrieved documents
            show_docs = console.input("\nTampilkan dokumen yang diambil? (y/n): ").lower() == 'y'
            if show_docs:
                console.print("\n[bold]Dokumen yang diambil:[/bold]")
                for i, doc in enumerate(result["retrieved_documents"]):
                    metadata = doc.get("metadata", {})
                    doc_metadata = doc.get("document_metadata", {})
                    filename = doc_metadata.get("filename", "Unknown")
                    
                    page_info = metadata.get("page", metadata.get("pages", ["Unknown"]))
                    if isinstance(page_info, list):
                        page_info = ", ".join(map(str, page_info))
                    
                    console.print(f"\n[bold]#{i+1} (Score: {doc['score']:.4f})[/bold]")
                    if "original_score" in doc:
                        console.print(f"Original Score: {doc['original_score']:.4f}")
                    if "vector_score" in doc:
                        console.print(f"Vector Score: {doc.get('vector_score', 0):.4f}, Keyword Score: {doc.get('keyword_score', 0):.4f}")
                    console.print(f"[bold blue]Dokumen:[/bold blue] {filename}, [bold blue]Halaman:[/bold blue] {page_info}")
                    console.print(f"[dim]{doc['text'][:300]}{'...' if len(doc['text']) > 300 else ''}[/dim]")
            
        except KeyboardInterrupt:
            break
        except Exception as e:
            logger.error(f"Error in chat loop: {e}")
            console.print(f"[bold red]Error:[/bold red] {str(e)}")

if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Enhanced RAG System for Qdrant")
    parser.add_argument("--collection", type=str, default="tes_combine", help="Qdrant collection name")
    parser.add_argument("--host", type=str, default="localhost", help="Qdrant host")
    parser.add_argument("--port", type=int, default=6333, help="Qdrant port")
    args = parser.parse_args()
    
    # Load environment variables
    load_dotenv()
    
    # Initialize enhanced RAG system
    rag_system = ImprovedRAGSystem(
        collection_name=args.collection,
        host=args.host,
        port=args.port
    )
    
    # Start chat loop
    chat_loop(rag_system)