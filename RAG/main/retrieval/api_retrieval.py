from fastapi import FastAPI, HTTPException, status
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel, Field
from typing import List, Dict, Any, Optional
import logging
import time
from contextlib import asynccontextmanager

# Import your existing RAG components
from engine_retrieval import ImprovedRAGSystem  # Replace with actual filename
from dotenv import load_dotenv

# Setup logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    handlers=[logging.FileHandler("rag_api.log"), logging.StreamHandler()]
)
logger = logging.getLogger("RAG_API")

# Global variable to hold RAG system
rag_system: Optional[ImprovedRAGSystem] = None

# Pydantic Models for Request/Response
class ChatRequest(BaseModel):
    query: str = Field(..., description="User query", min_length=1, max_length=1000)
    use_query_expansion: bool = Field(True, description="Enable query expansion")
    use_hybrid_search: bool = Field(True, description="Enable hybrid search (vector + keyword)")
    use_reranking: bool = Field(True, description="Enable reranking of results")
    evaluate_response: bool = Field(False, description="Enable response evaluation")
    limit: int = Field(5, description="Number of documents to retrieve", ge=1, le=20)
    filter_params: Optional[Dict[str, Any]] = Field(None, description="Optional filters for document retrieval")

class DocumentResult(BaseModel):
    id: str
    score: float
    text: str
    metadata: Dict[str, Any]
    document_metadata: Dict[str, Any]
    original_score: Optional[float] = None
    vector_score: Optional[float] = None
    keyword_score: Optional[float] = None

class ResponseEvaluation(BaseModel):
    relevance: Optional[float] = None
    factual_accuracy: Optional[float] = None
    completeness: Optional[float] = None
    hallucination: Optional[float] = None
    justification: Optional[str] = None
    error: Optional[str] = None

class ChatResponse(BaseModel):
    query: str
    answer: str
    retrieved_documents: List[DocumentResult]
    execution_time: float
    evaluation: Optional[ResponseEvaluation] = None
    timestamp: str

class HealthResponse(BaseModel):
    status: str
    message: str
    qdrant_connected: bool
    timestamp: str

class ErrorResponse(BaseModel):
    error: str
    detail: str
    timestamp: str

# Startup and shutdown events
@asynccontextmanager
async def lifespan(app: FastAPI):
    # Startup
    global rag_system
    try:
        load_dotenv()
        logger.info("Initializing RAG system...")
        
        # Initialize RAG system with default collection
        # You can make these configurable via environment variables
        collection_name = "tes_combine"  # or from env var
        host = "localhost"  # or from env var
        port = 6333  # or from env var
        
        rag_system = ImprovedRAGSystem(
            collection_name=collection_name,
            host=host,
            port=port
        )
        logger.info("RAG system initialized successfully")
        
    except Exception as e:
        logger.error(f"Failed to initialize RAG system: {e}")
        raise RuntimeError(f"Failed to initialize RAG system: {e}")
    
    yield
    
    # Shutdown
    logger.info("Shutting down RAG API")

# Create FastAPI app
app = FastAPI(
    title="Enhanced RAG API",
    description="API for Retrieval-Augmented Generation with Qdrant",
    version="1.0.0",
    lifespan=lifespan
)

# Add CORS middleware
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],  # Configure appropriately for production
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# API Endpoints
@app.get("/", summary="Root endpoint")
async def root():
    """Root endpoint with basic API information"""
    return {
        "message": "Enhanced RAG API",
        "version": "1.0.0",
        "endpoints": {
            "chat": "/chat",
            "health": "/health",
            "docs": "/docs"
        }
    }

@app.get("/health", response_model=HealthResponse, summary="Health check")
async def health_check():
    """Check API and Qdrant connection health"""
    global rag_system
    
    if rag_system is None:
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail="RAG system not initialized"
        )
    
    # Test Qdrant connection
    qdrant_connected = True
    try:
        # Try to get collection info to test connection
        rag_system.retriever.client.get_collection(rag_system.retriever.collection_name)
    except Exception as e:
        logger.warning(f"Qdrant connection test failed: {e}")
        qdrant_connected = False
    
    return HealthResponse(
        status="healthy" if qdrant_connected else "degraded",
        message="RAG API is running",
        qdrant_connected=qdrant_connected,
        timestamp=time.strftime('%Y-%m-%d %H:%M:%S')
    )

@app.post("/chat", response_model=ChatResponse, summary="Process chat query")
async def chat(request: ChatRequest):
    """
    Process a user query through the enhanced RAG pipeline.
    
    This endpoint:
    1. Expands the query (optional)
    2. Retrieves relevant documents using hybrid search
    3. Reranks results (optional)
    4. Generates contextual answer
    5. Evaluates response quality (optional)
    """
    global rag_system
    
    if rag_system is None:
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail="RAG system not initialized"
        )
    
    try:
        logger.info(f"Processing query: {request.query}")
        start_time = time.time()
        
        # Process query through RAG system
        result = rag_system.process_query(
            query=request.query,
            use_query_expansion=request.use_query_expansion,
            use_hybrid_search=request.use_hybrid_search,
            use_reranking=request.use_reranking,
            limit=request.limit,
            filter_params=request.filter_params,
            evaluate_response=request.evaluate_response
        )
        
        # Convert retrieved documents to response format
        documents = []
        for doc in result["retrieved_documents"]:
            documents.append(DocumentResult(
                id=str(doc["id"]),
                score=doc["score"],
                text=doc["text"],
                metadata=doc.get("metadata", {}),
                document_metadata=doc.get("document_metadata", {}),
                original_score=doc.get("original_score"),
                vector_score=doc.get("vector_score"),
                keyword_score=doc.get("keyword_score")
            ))
        
        # Convert evaluation if present
        evaluation = None
        if "evaluation" in result and result["evaluation"]:
            eval_data = result["evaluation"]
            evaluation = ResponseEvaluation(
                relevance=eval_data.get("relevance"),
                factual_accuracy=eval_data.get("factual_accuracy"),
                completeness=eval_data.get("completeness"),
                hallucination=eval_data.get("hallucination"),
                justification=eval_data.get("justification"),
                error=eval_data.get("error")
            )
        
        response = ChatResponse(
            query=result["query"],
            answer=result["answer"],
            retrieved_documents=documents,
            execution_time=result["execution_time"],
            evaluation=evaluation,
            timestamp=time.strftime('%Y-%m-%d %H:%M:%S')
        )
        
        execution_time = time.time() - start_time
        logger.info(f"Query processed successfully in {execution_time:.2f} seconds")
        
        return response
        
    except Exception as e:
        logger.error(f"Error processing query: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Error processing query: {str(e)}"
        )

@app.post("/chat/simple", summary="Simple chat endpoint")
async def simple_chat(query: str):
    """
    Simplified chat endpoint that accepts just a query string.
    Uses default RAG settings for quick testing.
    """
    request = ChatRequest(query=query)
    return await chat(request)

@app.get("/collections/{collection_name}/info", summary="Get collection information")
async def get_collection_info(collection_name: str):
    """Get information about a Qdrant collection"""
    global rag_system
    
    if rag_system is None:
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail="RAG system not initialized"
        )
    
    try:
        collection_info = rag_system.retriever.client.get_collection(collection_name)
        return {
            "collection_name": collection_name,
            "points_count": collection_info.points_count,
            "vectors_count": collection_info.vectors_count,
            "status": collection_info.status,
            "config": {
                "distance": collection_info.config.params.vectors.distance,
                "size": collection_info.config.params.vectors.size
            }
        }
    except Exception as e:
        logger.error(f"Error getting collection info: {e}")
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Collection not found or error: {str(e)}"
        )

# Exception handlers
@app.exception_handler(HTTPException)
async def http_exception_handler(request, exc):
    return ErrorResponse(
        error=exc.detail,
        detail=f"HTTP {exc.status_code}",
        timestamp=time.strftime('%Y-%m-%d %H:%M:%S')
    )

@app.exception_handler(Exception)
async def general_exception_handler(request, exc):
    logger.error(f"Unhandled exception: {exc}")
    return ErrorResponse(
        error="Internal server error",
        detail=str(exc),
        timestamp=time.strftime('%Y-%m-%d %H:%M:%S')
    )

if __name__ == "__main__":
    import uvicorn
    
    # Run the API
    uvicorn.run(
        "main:app",  # Replace "main" with your actual filename
        host="0.0.0.0",
        port=8000,
        reload=True,  # Set to False in production
        log_level="info"
    )