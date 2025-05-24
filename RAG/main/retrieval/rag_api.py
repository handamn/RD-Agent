## How to use
## uvicorn rag_api:app --host 0.0.0.0 --port 8000 --reload


from fastapi import FastAPI, HTTPException
from pydantic import BaseModel, Field
from typing import Optional, Dict, List, Any
import logging
import time
from contextlib import asynccontextmanager

# Import your RAG system
from engine_retrieval import ImprovedRAGSystem

# Pydantic models for request/response
class QueryRequest(BaseModel):
    query: str = Field(..., description="User query")
    use_query_expansion: bool = Field(True, description="Enable query expansion")
    use_hybrid_search: bool = Field(True, description="Enable hybrid search")
    use_reranking: bool = Field(True, description="Enable reranking")
    evaluate_response: bool = Field(False, description="Enable response evaluation")
    limit: int = Field(5, ge=1, le=20, description="Number of documents to retrieve")
    filter_params: Optional[Dict[str, Any]] = Field(None, description="Filter parameters")

class DocumentInfo(BaseModel):
    id: str
    score: float
    text: str
    metadata: Dict[str, Any]
    document_metadata: Dict[str, Any]
    original_score: Optional[float] = None
    vector_score: Optional[float] = None
    keyword_score: Optional[float] = None

class EvaluationInfo(BaseModel):
    relevance: Optional[float] = None
    factual_accuracy: Optional[float] = None
    completeness: Optional[float] = None
    hallucination: Optional[float] = None
    justification: Optional[str] = None
    error: Optional[str] = None

class QueryResponse(BaseModel):
    query: str
    answer: str
    retrieved_documents: List[DocumentInfo]
    execution_time: float
    evaluation: Optional[EvaluationInfo] = None
    status: str = "success"
    timestamp: str

class HealthResponse(BaseModel):
    status: str
    timestamp: str
    collection_name: str

class ErrorResponse(BaseModel):
    error: str
    detail: Optional[str] = None
    timestamp: str

# Global variable for RAG system
rag_system = None

@asynccontextmanager
async def lifespan(app: FastAPI):
    # Startup
    global rag_system
    try:
        logging.info("Initializing RAG system...")
        rag_system = ImprovedRAGSystem(
            collection_name="tes_combine",  # Sesuaikan dengan collection Anda
            host="localhost",
            port=6333
        )
        logging.info("RAG system initialized successfully")
        yield
    except Exception as e:
        logging.error(f"Failed to initialize RAG system: {e}")
        raise e
    finally:
        # Shutdown
        logging.info("Shutting down RAG system...")

# Create FastAPI app
app = FastAPI(
    title="Enhanced RAG API",
    description="API for Retrieval-Augmented Generation system with Qdrant",
    version="1.0.0",
    lifespan=lifespan
)

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger("RAG-API")

@app.get("/", response_model=Dict[str, str])
async def root():
    """Root endpoint"""
    return {
        "message": "Enhanced RAG API",
        "version": "1.0.0",
        "docs": "/docs"
    }

@app.get("/health", response_model=HealthResponse)
async def health_check():
    """Health check endpoint"""
    if rag_system is None:
        raise HTTPException(status_code=503, detail="RAG system not initialized")
    
    return HealthResponse(
        status="healthy",
        timestamp=time.strftime("%Y-%m-%d %H:%M:%S"),
        collection_name="tes_combine"
    )

@app.post("/query", response_model=QueryResponse)
async def process_query(request: QueryRequest):
    """Process a query through the RAG system"""
    if rag_system is None:
        raise HTTPException(status_code=503, detail="RAG system not initialized")
    
    try:
        # Process the query
        result = rag_system.process_query(
            query=request.query,
            use_query_expansion=request.use_query_expansion,
            use_hybrid_search=request.use_hybrid_search,
            use_reranking=request.use_reranking,
            limit=request.limit,
            filter_params=request.filter_params,
            evaluate_response=request.evaluate_response
        )
        
        # Convert documents to Pydantic models
        documents = []
        for doc in result["retrieved_documents"]:
            doc_info = DocumentInfo(
                id=str(doc["id"]),
                score=doc["score"],
                text=doc["text"],
                metadata=doc.get("metadata", {}),
                document_metadata=doc.get("document_metadata", {}),
                original_score=doc.get("original_score"),
                vector_score=doc.get("vector_score"),
                keyword_score=doc.get("keyword_score")
            )
            documents.append(doc_info)
        
        # Convert evaluation if present
        evaluation = None
        if "evaluation" in result:
            eval_data = result["evaluation"]
            evaluation = EvaluationInfo(
                relevance=eval_data.get("relevance"),
                factual_accuracy=eval_data.get("factual_accuracy"),
                completeness=eval_data.get("completeness"),
                hallucination=eval_data.get("hallucination"),
                justification=eval_data.get("justification"),
                error=eval_data.get("error")
            )
        
        return QueryResponse(
            query=result["query"],
            answer=result["answer"],
            retrieved_documents=documents,
            execution_time=result["execution_time"],
            evaluation=evaluation,
            timestamp=time.strftime("%Y-%m-%d %H:%M:%S")
        )
        
    except Exception as e:
        logger.error(f"Error processing query: {e}")
        raise HTTPException(
            status_code=500,
            detail=f"Error processing query: {str(e)}"
        )

@app.post("/query-simple", response_model=Dict[str, Any])
async def process_simple_query(query: str):
    """Simplified query endpoint with default settings"""
    if rag_system is None:
        raise HTTPException(status_code=503, detail="RAG system not initialized")
    
    try:
        result = rag_system.process_query(query=query)
        
        return {
            "query": query,
            "answer": result["answer"],
            "execution_time": result["execution_time"],
            "document_count": len(result["retrieved_documents"]),
            "timestamp": time.strftime("%Y-%m-%d %H:%M:%S")
        }
        
    except Exception as e:
        logger.error(f"Error processing simple query: {e}")
        raise HTTPException(
            status_code=500,
            detail=f"Error processing query: {str(e)}"
        )

@app.get("/settings", response_model=Dict[str, Any])
async def get_default_settings():
    """Get default RAG settings"""
    return {
        "use_query_expansion": True,
        "use_hybrid_search": True,
        "use_reranking": True,
        "evaluate_response": False,
        "limit": 5,
        "filter_params": None
    }

if __name__ == "__main__":
    import uvicorn
    uvicorn.run(
        "rag_api:app",  # Ganti dengan nama file Python Anda
        host="0.0.0.0",
        port=8000,
        reload=True,
        log_level="info"
    )


## example use
"""
# Health Check (GET)

URL: http://localhost:8000/health
Method: GET
Expected Response:

json{
    "status": "healthy",
    "timestamp": "2024-01-01 12:00:00",
    "collection_name": "tes_combine"
}


# Simple Query (POST)

URL: http://localhost:8000/query-simple
Method: POST
Body: Form-data atau x-www-form-urlencoded

Key: query
Value: "Apa itu investasi saham?"



# Advanced Query (POST)

URL: http://localhost:8000/query
Method: POST
Headers: Content-Type: application/json
Body (JSON):

json{
    "query": "Bagaimana cara investasi saham untuk pemula?",
    "use_query_expansion": true,
    "use_hybrid_search": true,
    "use_reranking": true,
    "evaluate_response": false,
    "limit": 5,
    "filter_params": null
}
Query dengan Filter (POST)
json{
    "query": "Risiko investasi",
    "use_query_expansion": true,
    "use_hybrid_search": true,
    "use_reranking": true,
    "evaluate_response": true,
    "limit": 3,
    "filter_params": {
        "document_metadata.filename": "panduan_investasi.pdf"
    }
}
"""