import os
import json
import time
import logging
import argparse
from typing import List, Dict, Any, Tuple, Optional

from dotenv import load_dotenv
from rich.console import Console
from rich.markdown import Markdown
from openai import OpenAI
from qdrant_client import QdrantClient
from qdrant_client.http.models import Filter, FieldCondition, MatchValue

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

class QdrantRetriever:
    """Class to retrieve documents from Qdrant"""
    
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
        filter_condition = None
        if filter_params:
            # Example: filter_params = {"metadata.document": "ABF Indonesia Bond Index Fund.pdf"}
            conditions = []
            for field, value in filter_params.items():
                conditions.append(FieldCondition(key=field, match=MatchValue(value=value)))
            
            if conditions:
                filter_condition = Filter(must=conditions)
        
        try:
            results = self.client.search(
                collection_name=self.collection_name,
                query_vector=query_vector,
                limit=limit,
                filter=filter_condition
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
                    
                    Return only a JSON array of scores, nothing else. For example: [95, 80, 45, 20]
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

class RAGSystem:
    """Main RAG system class"""
    
    def __init__(self, collection_name: str, host="localhost", port=6333):
        """Initialize RAG system components"""
        self.embedding_generator = EmbeddingGenerator()
        self.retriever = QdrantRetriever(collection_name, host, port)
        self.query_expander = QueryExpander()
        self.reranker = Reranker()
        self.client = OpenAI(api_key=os.getenv("OPENAI_API_KEY"))
        logger.info("RAG system initialized")
    
    def process_query(self, query: str, use_query_expansion: bool = True, 
                      use_reranking: bool = True, limit: int = 5,
                      filter_params: Optional[Dict] = None) -> Dict:
        """Process a query through the RAG pipeline"""
        start_time = time.time()
        logger.info(f"Processing query: {query}")
        
        # Step 1: Query Expansion (optional)
        if use_query_expansion:
            expanded_queries = self.query_expander.expand_query(query)
            logger.info(f"Expanded queries: {expanded_queries}")
        else:
            expanded_queries = [query]
        
        # Step 2: Retrieve documents for each expanded query
        all_retrieved_docs = []
        for q in expanded_queries:
            # Generate embedding
            query_embedding = self.embedding_generator.get_embedding(q)
            
            # Retrieve documents
            docs = self.retriever.retrieve(query_embedding, limit=limit, filter_params=filter_params)
            all_retrieved_docs.extend(docs)
        
        # Remove duplicates based on content
        unique_docs = []
        seen_ids = set()
        for doc in all_retrieved_docs:
            if doc["id"] not in seen_ids:
                unique_docs.append(doc)
                seen_ids.add(doc["id"])
        
        # Step 3: Reranking (optional)
        if use_reranking and unique_docs:
            reranked_docs = self.reranker.rerank(query, unique_docs)
            # Limit to top results after reranking
            retrieved_docs = reranked_docs[:limit]
        else:
            # Sort by score and limit
            unique_docs.sort(key=lambda x: x["score"], reverse=True)
            retrieved_docs = unique_docs[:limit]
        
        # Step 4: Generate response
        context = self._prepare_context(retrieved_docs)
        answer = self._generate_answer(query, context, retrieved_docs)
        
        execution_time = time.time() - start_time
        logger.info(f"Query processed in {execution_time:.2f} seconds")
        
        # Return complete result
        return {
            "query": query,
            "answer": answer,
            "retrieved_documents": retrieved_docs,
            "execution_time": execution_time
        }
    
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
    """Interactive chat loop"""
    console.print("\n[bold green]RAG Chat System[/bold green]")
    console.print("Ketik 'exit' untuk keluar, 'settings' untuk mengubah pengaturan RAG\n")
    
    # Default settings
    settings = {
        "use_query_expansion": True,
        "use_reranking": True,
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
                settings["use_reranking"] = console.input("Gunakan reranking? (y/n): ").lower() == 'y'
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
                use_reranking=settings["use_reranking"],
                limit=settings["limit"],
                filter_params=settings["filter_params"]
            )
            
            # Display answer
            console.print("\n[bold cyan][RAG]:[/bold cyan]")
            console.print(Markdown(result["answer"]))
            
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
                    console.print(f"[bold blue]Dokumen:[/bold blue] {filename}, [bold blue]Halaman:[/bold blue] {page_info}")
                    console.print(f"[dim]{doc['text'][:300]}{'...' if len(doc['text']) > 300 else ''}[/dim]")
            
        except KeyboardInterrupt:
            break
        except Exception as e:
            logger.error(f"Error in chat loop: {e}")
            console.print(f"[bold red]Error:[/bold red] {str(e)}")

if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="RAG System for Qdrant")
    parser.add_argument("--collection", type=str, default="tomoro_try", help="Qdrant collection name")
    parser.add_argument("--host", type=str, default="localhost", help="Qdrant host")
    parser.add_argument("--port", type=int, default=6333, help="Qdrant port")
    args = parser.parse_args()
    
    # Load environment variables
    load_dotenv()
    
    # Initialize RAG system
    rag_system = RAGSystem(
        collection_name=args.collection,
        host=args.host,
        port=args.port
    )
    
    # Start chat loop
    chat_loop(rag_system)