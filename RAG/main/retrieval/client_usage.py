import requests
import json
from typing import Optional, Dict, Any

class RAGClient:
    """Client for interacting with the RAG API"""
    
    def __init__(self, base_url: str = "http://localhost:8000"):
        self.base_url = base_url.rstrip('/')
        self.session = requests.Session()
    
    def health_check(self) -> Dict[str, Any]:
        """Check API health"""
        response = self.session.get(f"{self.base_url}/health")
        response.raise_for_status()
        return response.json()
    
    def chat(self, 
             query: str,
             use_query_expansion: bool = True,
             use_hybrid_search: bool = True,
             use_reranking: bool = True,
             evaluate_response: bool = False,
             limit: int = 5,
             filter_params: Optional[Dict[str, Any]] = None) -> Dict[str, Any]:
        """Send a chat query to the RAG system"""
        
        payload = {
            "query": query,
            "use_query_expansion": use_query_expansion,
            "use_hybrid_search": use_hybrid_search,
            "use_reranking": use_reranking,
            "evaluate_response": evaluate_response,
            "limit": limit
        }
        
        if filter_params:
            payload["filter_params"] = filter_params
        
        response = self.session.post(
            f"{self.base_url}/chat",
            json=payload,
            headers={"Content-Type": "application/json"}
        )
        response.raise_for_status()
        return response.json()
    
    def simple_chat(self, query: str) -> Dict[str, Any]:
        """Simple chat with default settings"""
        response = self.session.post(
            f"{self.base_url}/chat/simple",
            params={"query": query}
        )
        response.raise_for_status()
        return response.json()
    
    def get_collection_info(self, collection_name: str) -> Dict[str, Any]:
        """Get information about a collection"""
        response = self.session.get(f"{self.base_url}/collections/{collection_name}/info")
        response.raise_for_status()
        return response.json()

# Example usage
if __name__ == "__main__":
    # Initialize client
    client = RAGClient("http://localhost:8000")
    
    # Health check
    try:
        health = client.health_check()
        print("✅ API Health:", health)
    except Exception as e:
        print("❌ Health check failed:", e)
        exit(1)
    
    # Example queries
    queries = [
        "Apa itu investasi reksa dana?",
        "Bagaimana cara menghitung return investasi?",
        "Apa perbedaan saham dan obligasi?"
    ]
    
    for query in queries:
        print(f"\n{'='*50}")
        print(f"Query: {query}")
        print('='*50)
        
        try:
            # Basic chat
            result = client.chat(
                query=query,
                use_query_expansion=True,
                use_hybrid_search=True,
                use_reranking=True,
                evaluate_response=True,
                limit=3
            )
            
            print(f"\n📝 Answer:")
            print(result["answer"])
            
            print(f"\n⏱️ Execution Time: {result['execution_time']:.2f} seconds")
            
            # Show evaluation if available
            if result.get("evaluation"):
                eval_data = result["evaluation"]
                print(f"\n📊 Evaluation:")
                print(f"  Relevance: {eval_data.get('relevance', 'N/A')}/10")
                print(f"  Factual Accuracy: {eval_data.get('factual_accuracy', 'N/A')}/10")
                print(f"  Completeness: {eval_data.get('completeness', 'N/A')}/10")
                print(f"  Hallucination: {eval_data.get('hallucination', 'N/A')}/10")
            
            # Show source documents
            print(f"\n📚 Retrieved Documents ({len(result['retrieved_documents'])}):")
            for i, doc in enumerate(result["retrieved_documents"]):
                filename = doc["document_metadata"].get("filename", "Unknown")
                page = doc["metadata"].get("page", "Unknown")
                score = doc["score"]
                
                print(f"  {i+1}. {filename} (Page: {page}) - Score: {score:.4f}")
                print(f"     Preview: {doc['text'][:100]}...")
                
        except Exception as e:
            print(f"❌ Error: {e}")
    
    # Example with filters
    print(f"\n{'='*50}")
    print("Example with Document Filter")
    print('='*50)
    
    try:
        # Filter by specific document
        result = client.chat(
            query="Apa itu diversifikasi investasi?",
            filter_params={"document_metadata.filename": "investment_guide.pdf"},
            limit=2
        )
        
        print(f"📝 Filtered Answer:")
        print(result["answer"])
        
    except Exception as e:
        print(f"❌ Filter example failed: {e}")

# Example with curl commands (for testing)
curl_examples = '''
# Health Check
curl -X GET "http://localhost:8000/health"

# Simple Chat
curl -X POST "http://localhost:8000/chat/simple?query=Apa%20itu%20investasi%20reksa%20dana?"

# Advanced Chat
curl -X POST "http://localhost:8000/chat" \
  -H "Content-Type: application/json" \
  -d '{
    "query": "Bagaimana cara menghitung return investasi?",
    "use_query_expansion": true,
    "use_hybrid_search": true,
    "use_reranking": true,
    "evaluate_response": true,
    "limit": 5
  }'

# Chat with Filter
curl -X POST "http://localhost:8000/chat" \
  -H "Content-Type: application/json" \
  -d '{
    "query": "Apa itu diversifikasi?",
    "filter_params": {
      "document_metadata.filename": "investment_guide.pdf"
    },
    "limit": 3
  }'

# Collection Info
curl -X GET "http://localhost:8000/collections/tes_combine/info"
'''

print("\n" + "="*50)
print("CURL Examples:")
print("="*50)
print(curl_examples)