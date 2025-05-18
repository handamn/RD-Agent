# """
# RAG System dengan Qdrant dan OpenAI

# Script ini menyediakan fungsi-fungsi untuk:
# 1. Melakukan pencarian semantic di database Qdrant
# 2. Re-ranking hasil pencarian
# 3. Menghasilkan jawaban dengan LLM menggunakan konteks yang ditemukan
# """

import os
import json
import time
import textwrap
from typing import List, Dict, Any, Tuple, Union
from dataclasses import dataclass
import hashlib
import numpy as np
from datetime import datetime
from tqdm import tqdm
from dotenv import load_dotenv

# OpenAI untuk embedding dan LLM
from openai import OpenAI

# Qdrant untuk retrieval
from qdrant_client import QdrantClient
from qdrant_client.http import models as qmodels

# ===== Logger =====
class Logger:
    def __init__(self, log_dir="log"):
        os.makedirs(log_dir, exist_ok=True)
        log_filename = datetime.now().strftime("%Y-%m-%d_%H-%M-%S") + "_RAG.log"
        self.LOG_FILE = os.path.join(log_dir, log_filename)

    def log_info(self, message, status="INFO"):
        timestamp = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
        log_message = f"[{timestamp}] [{status}] {message}\n"
        with open(self.LOG_FILE, "a", encoding="utf-8") as log_file:
            log_file.write(log_message)
        print(log_message.strip())

# ===== Embedder =====
class Embedder:
    def __init__(self, api_key=None, embedding_model="text-embedding-3-small"):
        # Use the provided API key or look for it in environment variables
        self.client = OpenAI(api_key=api_key)
        self.embedding_model = embedding_model

    def embed_text(self, text: str) -> list[float]:
        """Generate embedding for a single text"""
        response = self.client.embeddings.create(
            input=[text],
            model=self.embedding_model
        )
        return response.data[0].embedding
    
    def embed_batch(self, texts: List[str], batch_size=16) -> List[List[float]]:
        """Generate embeddings for a batch of texts"""
        all_embeddings = []
        
        for i in range(0, len(texts), batch_size):
            batch = texts[i:i+batch_size]
            response = self.client.embeddings.create(
                input=batch,
                model=self.embedding_model
            )
            batch_embeddings = [item.embedding for item in response.data]
            all_embeddings.extend(batch_embeddings)
        
        return all_embeddings

# ===== Retriever =====
class QdrantRetriever:
    def __init__(self, 
                 collection_name: str,
                 embedder: Embedder,
                 host="localhost", 
                 port=6333,
                 limit=10,
                 score_threshold=0.7):
        self.qdrant = QdrantClient(host=host, port=port)
        self.collection_name = collection_name
        self.embedder = embedder
        self.limit = limit
        self.score_threshold = score_threshold
        self.logger = Logger()
        
        # Check if collection exists
        if not self.qdrant.collection_exists(collection_name):
            self.logger.log_info(f"Collection '{collection_name}' does not exist!", status="ERROR")
        else:
            self.logger.log_info(f"Connected to collection '{collection_name}'")

    def retrieve(self, query: str) -> List[Dict[str, Any]]:
        """Retrieve documents from Qdrant based on query"""
        try:
            # Generate embedding for the query
            query_vector = self.embedder.embed_text(query)
            
            # Search in Qdrant
            search_result = self.qdrant.search(
                collection_name=self.collection_name,
                query_vector=query_vector,
                limit=self.limit,
                score_threshold=self.score_threshold,
                with_payload=True,
                with_vectors=False,
            )
            
            # Extract and format results
            results = []
            for hit in search_result:
                # Extract the content and metadata
                payload = hit.payload
                
                # Determine the content field based on payload structure
                content = payload.get("text", "")
                if not content:  # If using new format
                    content = payload.get("payload", {}).get("text", "") or payload.get("content", "")
                
                # Handle metadata
                metadata = payload.get("metadata", {})
                doc_metadata = payload.get("document_metadata", {})
                
                # Create a structured result
                result = {
                    "content": content,
                    "score": hit.score,
                    "item_id": payload.get("item_id", ""),
                    "metadata": metadata,
                    "document_metadata": doc_metadata
                }
                results.append(result)
            
            self.logger.log_info(f"Retrieved {len(results)} documents for query: '{query}'")
            return results
        
        except Exception as e:
            self.logger.log_info(f"Error retrieving documents: {e}", status="ERROR")
            return []
    
    def retrieve_hybrid(self, query: str, keyword_weight=0.3) -> List[Dict[str, Any]]:
        """
        Hybrid retrieval combining semantic and keyword search
        This requires Qdrant with qdrant-nlp plugin enabled
        """
        try:
            # Generate embedding for the query
            query_vector = self.embedder.embed_text(query)
            
            # Setup hybrid search
            semantic_query = qmodels.VectorQuery(
                vector=query_vector,
                field="vector", 
                weight=1.0 - keyword_weight
            )
            
            keyword_query = qmodels.MatchText(
                text=query,
                field="text"
            )
            keyword_search = qmodels.Filter(
                must=[keyword_query]
            )
            
            # Execute hybrid search
            search_result = self.qdrant.search(
                collection_name=self.collection_name,
                query_vector=None,  # Not used in hybrid
                limit=self.limit,
                query_filter=keyword_search,
                score_threshold=self.score_threshold,
                with_payload=True,
                with_vectors=False,
                vector_name="embedding",
                search_params=qmodels.SearchParams(
                    vector=semantic_query,
                    # This requires qdrant-nlp plugin to be enabled
                )
            )
            
            # Format results
            results = []
            for hit in search_result:
                payload = hit.payload
                content = payload.get("text", "") or payload.get("content", "")
                
                result = {
                    "content": content,
                    "score": hit.score,
                    "item_id": payload.get("item_id", ""),
                    "metadata": payload.get("metadata", {}),
                    "document_metadata": payload.get("document_metadata", {})
                }
                results.append(result)
            
            self.logger.log_info(f"Retrieved {len(results)} documents via hybrid search")
            return results
            
        except Exception as e:
            self.logger.log_info(f"Error in hybrid retrieval: {e}", status="ERROR")
            self.logger.log_info("Falling back to vector-only retrieval")
            return self.retrieve(query)  # Fallback to standard retrieval

# ===== Re-ranker =====
class Reranker:
    def __init__(self, api_key=None, model="gpt-4o-mini"):
        self.client = OpenAI(api_key=api_key)
        self.model = model
        self.logger = Logger()
    
    def rerank_with_llm(self, query: str, documents: List[Dict[str, Any]], top_n=5) -> List[Dict[str, Any]]:
        """Re-rank documents using LLM to evaluate relevance"""
        if not documents:
            return []
        
        try:
            # Prepare document summaries
            doc_texts = [f"Document {i+1}: {doc['content'][:300]}..." for i, doc in enumerate(documents)]
            
            # Prepare the prompt
            prompt = f"""
            Query: {query}
            
            Below are documents retrieved from a search. Rank them by relevance to the query, 
            listing only the document numbers (1-{len(documents)}) from most to least relevant.
            Consider semantic meaning, not just keyword matching.
            
            {'\n\n'.join(doc_texts)}
            
            Respond with ONLY a comma-separated list of document numbers in order of relevance.
            Example: 3,1,5,2,4
            """
            
            # Get re-ranking from LLM
            response = self.client.chat.completions.create(
                model=self.model,
                messages=[{"role": "user", "content": prompt}],
                temperature=0.0,
                max_tokens=50
            )
            
            result = response.choices[0].message.content.strip()
            
            # Parse the result to get document indices
            try:
                # Extract numbers and handle possible text in response
                import re
                numbers = re.findall(r'\d+', result)
                reranked_indices = [int(num) - 1 for num in numbers if 0 < int(num) <= len(documents)]
                
                # Ensure all documents are included (add any missing ones at the end)
                all_indices = set(range(len(documents)))
                missing_indices = all_indices - set(reranked_indices)
                reranked_indices.extend(missing_indices)
                
                # Limit to top_n
                reranked_indices = reranked_indices[:top_n]
                
                # Create new list with reranked documents
                reranked_docs = [documents[i] for i in reranked_indices]
                
                self.logger.log_info(f"Re-ranked documents: {result}")
                return reranked_docs
                
            except Exception as e:
                self.logger.log_info(f"Error parsing re-ranking result: {e}", status="WARNING")
                return documents[:top_n]  # Return original order if parsing fails
                
        except Exception as e:
            self.logger.log_info(f"Error in re-ranking: {e}", status="ERROR")
            return documents[:top_n]  # Return original order on error

    def cross_encoder_rerank(self, query: str, documents: List[Dict[str, Any]], top_n=5) -> List[Dict[str, Any]]:
        """
        Note: This is a placeholder for a cross-encoder based re-ranker
        For production use, you would implement this with a library like SentenceTransformers
        """
        # This simulates re-ranking with a cross-encoder by calculating similarity scores
        # In a real implementation, you would use a proper cross-encoder model
        
        # For now, we'll just use the original scores and limit to top_n
        sorted_docs = sorted(documents, key=lambda x: x['score'], reverse=True)
        return sorted_docs[:top_n]

# ===== Response Generator =====
class ResponseGenerator:
    def __init__(self, api_key=None, model="gpt-4o-mini", temperature=0.7):
        self.client = OpenAI(api_key=api_key)
        self.model = model
        self.temperature = temperature
        self.logger = Logger()
    
    def format_context(self, documents: List[Dict[str, Any]], max_tokens=6000) -> str:
        """Format retrieved documents into context for LLM"""
        context_parts = []
        current_tokens = 0
        estimated_tokens_per_char = 0.25  # Rough estimate
        
        for i, doc in enumerate(documents):
            # Extract content and metadata
            content = doc['content']
            metadata = doc.get('metadata', {})
            doc_metadata = doc.get('document_metadata', {})
            
            # Format source information
            source_info = ""
            if doc_metadata:
                filename = doc_metadata.get('filename', '')
                page = metadata.get('page', '')
                if filename and page:
                    source_info = f" [Source: {filename}, Page: {page}]"
                elif filename:
                    source_info = f" [Source: {filename}]"
            
            # Format document with content and source
            doc_text = f"[Document {i+1}]: {content}{source_info}"
            
            # Estimate token count
            estimated_tokens = len(doc_text) * estimated_tokens_per_char
            
            # Add document if within token budget
            if current_tokens + estimated_tokens <= max_tokens:
                context_parts.append(doc_text)
                current_tokens += estimated_tokens
            else:
                break
        
        return "\n\n".join(context_parts)
    
    def generate_response(self, query: str, context: str) -> str:
        """Generate a response using the LLM with retrieved context"""
        try:
            # Create the prompt with context and query
            prompt = f"""
            Kamu adalah asisten AI yang membantu pengguna dengan informasi akurat dari dokumen yang tersedia.
            
            Berikut adalah konteks dari dokumen-dokumen yang relevan dengan pertanyaan:
            
            {context}
            
            Berdasarkan konteks di atas, tolong jawab pertanyaan ini dengan detail dan akurat:
            {query}
            
            Jawablah dengan bahasa Indonesia yang baik dan benar. Jika informasi tidak ada dalam konteks, katakan dengan jujur bahwa kamu tidak bisa menjawab berdasarkan dokumen yang tersedia. Jangan berspekulasi.
            """
            
            # Call the LLM
            response = self.client.chat.completions.create(
                model=self.model,
                messages=[{"role": "user", "content": prompt}],
                temperature=self.temperature,
                max_tokens=1000
            )
            
            answer = response.choices[0].message.content.strip()
            self.logger.log_info(f"Generated response of {len(answer)} characters")
            
            return answer
            
        except Exception as e:
            self.logger.log_info(f"Error generating response: {e}", status="ERROR")
            return "Maaf, terjadi kesalahan dalam menghasilkan jawaban. Silakan coba lagi."

# ===== Main RAG Pipeline =====
class RAGPipeline:
    def __init__(self, 
                 collection_name: str,
                 api_key=None,
                 qdrant_host="localhost",
                 qdrant_port=6333,
                 embedding_model="text-embedding-3-small",
                 llm_model="gpt-4o-mini",
                 temperature=0.7,
                 top_k=10,
                 rerank_top_n=5):
        
        # Initialize components
        self.api_key = api_key
        self.embedder = Embedder(api_key=api_key, embedding_model=embedding_model)
        self.retriever = QdrantRetriever(
            collection_name=collection_name,
            embedder=self.embedder,
            host=qdrant_host,
            port=qdrant_port,
            limit=top_k
        )
        self.reranker = Reranker(api_key=api_key)
        self.generator = ResponseGenerator(
            api_key=api_key, 
            model=llm_model,
            temperature=temperature
        )
        self.top_k = top_k
        self.rerank_top_n = rerank_top_n
        self.logger = Logger()
    
    def answer_query(self, query: str, use_reranking=True, use_hybrid=False) -> Dict[str, Any]:
        """Process a query through the full RAG pipeline"""
        start_time = time.time()
        
        # Step 1: Retrieve relevant documents
        self.logger.log_info(f"Processing query: '{query}'")
        
        if use_hybrid:
            retrieved_docs = self.retriever.retrieve_hybrid(query)
        else:
            retrieved_docs = self.retriever.retrieve(query)
        
        if not retrieved_docs:
            return {
                "answer": "Maaf, tidak dapat menemukan informasi yang relevan untuk pertanyaan Anda.",
                "sources": [],
                "process_time": time.time() - start_time
            }
        
        # Step 2: Re-rank documents (optional)
        if use_reranking and len(retrieved_docs) > 1:
            self.logger.log_info("Re-ranking documents...")
            reranked_docs = self.reranker.rerank_with_llm(query, retrieved_docs, self.rerank_top_n)
        else:
            reranked_docs = retrieved_docs[:self.rerank_top_n]
        
        # Step 3: Format documents into context
        context = self.generator.format_context(reranked_docs)
        
        # Step 4: Generate response
        self.logger.log_info("Generating response...")
        answer = self.generator.generate_response(query, context)
        
        # Step 5: Prepare sources information
        sources = []
        for doc in reranked_docs:
            source_info = {
                "content_preview": doc['content'][:200] + "...",
                "score": doc['score']
            }
            
            # Add metadata if available
            metadata = doc.get('metadata', {})
            doc_metadata = doc.get('document_metadata', {})
            
            if doc_metadata:
                source_info["filename"] = doc_metadata.get('filename', '')
            
            if metadata:
                source_info["page"] = metadata.get('page', '')
            
            sources.append(source_info)
        
        # Calculate processing time
        process_time = time.time() - start_time
        self.logger.log_info(f"Query processed in {process_time:.2f} seconds")
        
        # Return complete response
        return {
            "answer": answer,
            "sources": sources,
            "process_time": process_time
        }

# ===== Interactive CLI =====
def interactive_cli():
    """Run an interactive CLI to test the RAG system"""
    load_dotenv()
    
    # Get configuration
    api_key = os.getenv('OPENAI_API_KEY')
    collection = input("Enter Qdrant collection name (default: tomoro_try): ") or "tomoro_try"
    
    print("\nInitializing RAG Pipeline...")
    rag = RAGPipeline(
        collection_name=collection,
        api_key=api_key,
        llm_model="gpt-4o-mini"  # You can change to gpt-4 or others
    )
    
    print("\nRAG system ready! Type 'exit' to quit.\n")
    
    while True:
        query = input("\nMasukkan pertanyaan: ")
        if query.lower() in ['exit', 'quit', 'keluar']:
            break
        
        use_reranking = True  # Set to False to disable re-ranking
        
        # Process query
        result = rag.answer_query(query, use_reranking=use_reranking)
        
        # Display answer
        print("\n" + "="*80)
        print("JAWABAN:")
        print("-"*80)
        print(result["answer"])
        print("\n" + "="*80)
        
        # Display sources if available
        if result["sources"]:
            print("SUMBER DOKUMEN:")
            print("-"*80)
            for i, source in enumerate(result["sources"]):
                print(f"[{i+1}] {source.get('filename', 'Unknown')} " +
                      (f"(Page: {source.get('page', 'N/A')})" if source.get('page') else ""))
                preview = source.get('content_preview', '')
                print(textwrap.fill(preview, width=80, initial_indent="    ", subsequent_indent="    "))
                print()
        
        print(f"Waktu pemrosesan: {result['process_time']:.2f} detik")
        print("="*80 + "\n")

# ===== API Server =====
def start_api_server(host="0.0.0.0", port=8000):
    """Start a FastAPI server for the RAG system"""
    try:
        from fastapi import FastAPI, HTTPException, Query, Body
        from fastapi.middleware.cors import CORSMiddleware
        import uvicorn
        from pydantic import BaseModel
        
        # Load environment variables
        load_dotenv()
        api_key = os.getenv('OPENAI_API_KEY')
        collection = os.getenv('QDRANT_COLLECTION', 'tomoro_try')
        
        # Initialize RAG pipeline
        rag = RAGPipeline(
            collection_name=collection,
            api_key=api_key,
            llm_model="gpt-4o-mini"
        )
        
        # Define API models
        class QueryRequest(BaseModel):
            query: str
            use_reranking: bool = True
            use_hybrid: bool = False
        
        # Create FastAPI app
        app = FastAPI(
            title="RAG API",
            description="API for Retrieval-Augmented Generation with Qdrant and OpenAI",
            version="1.0.0"
        )
        
        # Add CORS middleware
        app.add_middleware(
            CORSMiddleware,
            allow_origins=["*"],
            allow_credentials=True,
            allow_methods=["*"],
            allow_headers=["*"],
        )
        
        # Define endpoints
        @app.post("/api/query")
        async def query(request: QueryRequest):
            if not request.query.strip():
                raise HTTPException(status_code=400, detail="Query cannot be empty")
            
            result = rag.answer_query(
                query=request.query,
                use_reranking=request.use_reranking,
                use_hybrid=request.use_hybrid
            )
            
            return result
        
        @app.get("/api/health")
        async def health_check():
            return {"status": "healthy", "timestamp": datetime.now().isoformat()}
        
        # Start the server
        print(f"Starting RAG API server on http://{host}:{port}")
        uvicorn.run(app, host=host, port=port)
        
    except ImportError:
        print("FastAPI and uvicorn are required to run the API server.")
        print("Install them with: pip install fastapi uvicorn")
        return

if __name__ == "__main__":
    import argparse
    
    parser = argparse.ArgumentParser(description="RAG System with Qdrant and OpenAI")
    parser.add_argument("--mode", choices=["cli", "api"], default="cli",
                      help="Run in CLI mode or as API server")
    parser.add_argument("--host", default="0.0.0.0", help="Host for API server")
    parser.add_argument("--port", type=int, default=8000, help="Port for API server")
    
    args = parser.parse_args()
    
    if args.mode == "cli":
        interactive_cli()
    elif args.mode == "api":
        start_api_server(host=args.host, port=args.port)