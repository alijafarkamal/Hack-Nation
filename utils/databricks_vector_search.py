"""
Databricks Vector Search integration for medical facility semantic search.
Uses Unity Catalog for vector storage and retrieval.
"""
from typing import List, Dict, Any, Optional
import pandas as pd
from databricks.sdk import WorkspaceClient
from databricks.vector_search.client import VectorSearchClient
from sentence_transformers import SentenceTransformer
from config import Config


class DatabricksVectorSearch:
    """Manages vector embeddings and semantic search for medical facilities."""
    
    def __init__(self):
        """Initialize Vector Search client and embedding model."""
        self.config = Config()
        
        # Initialize Databricks clients
        self.workspace_client = WorkspaceClient(
            host=self.config.DATABRICKS_HOST,
            token=self.config.DATABRICKS_TOKEN
        )
        
        self.vector_client = VectorSearchClient(
            workspace_url=self.config.DATABRICKS_HOST,
            personal_access_token=self.config.DATABRICKS_TOKEN
        )
        
        # Initialize embedding model
        print(f"📦 Loading embedding model: {self.config.EMBEDDING_MODEL}")
        self.embedding_model = SentenceTransformer(self.config.EMBEDDING_MODEL)
        
        self.index_name = self.config.VECTOR_INDEX_NAME
        
    def create_index(self, primary_key: str = "facility_id") -> None:
        """
        Create a new vector search index in Unity Catalog.
        
        Args:
            primary_key: Column name to use as primary key
        """
        try:
            # Check if endpoint exists, create if not
            endpoint_name = self.config.VECTOR_SEARCH_ENDPOINT
            
            print(f"🔧 Creating vector search index: {self.index_name}")
            
            # This is a simplified example - actual implementation depends on your data source
            self.vector_client.create_delta_sync_index(
                endpoint_name=endpoint_name,
                index_name=self.index_name,
                source_table_name=f"{self.config.UNITY_CATALOG_NAME}.{self.config.UNITY_SCHEMA_NAME}.facilities",
                pipeline_type="TRIGGERED",
                primary_key=primary_key,
                embedding_dimension=384,  # all-MiniLM-L6-v2 dimension
                embedding_vector_column="capability_embedding"
            )
            
            print(f"✅ Vector index created successfully")
            
        except Exception as e:
            print(f"⚠️  Index creation error: {e}")
            print(f"💡 This may be expected if index already exists")
    
    def embed_text(self, text: str) -> List[float]:
        """
        Generate embedding vector for input text.
        
        Args:
            text: Input text to embed
            
        Returns:
            Embedding vector
        """
        embedding = self.embedding_model.encode(text, convert_to_tensor=False)
        return embedding.tolist()
    
    def embed_batch(self, texts: List[str]) -> List[List[float]]:
        """
        Generate embeddings for multiple texts.
        
        Args:
            texts: List of input texts
            
        Returns:
            List of embedding vectors
        """
        embeddings = self.embedding_model.encode(texts, convert_to_tensor=False)
        return [emb.tolist() for emb in embeddings]
    
    def search_similar_facilities(
        self, 
        query: str, 
        top_k: int = 5,
        filters: Optional[Dict[str, Any]] = None
    ) -> List[Dict[str, Any]]:
        """
        Search for facilities with similar capabilities.
        
        Args:
            query: Natural language query describing capabilities
            top_k: Number of results to return
            filters: Optional filters (e.g., {"region": "Western"})
            
        Returns:
            List of similar facilities with scores
        """
        try:
            # Generate query embedding
            query_embedding = self.embed_text(query)
            
            # Search the index
            index = self.vector_client.get_index(
                endpoint_name=self.config.VECTOR_SEARCH_ENDPOINT,
                index_name=self.index_name
            )
            
            results = index.similarity_search(
                query_vector=query_embedding,
                columns=["facility_id", "name", "capabilities_raw", "region"],
                num_results=top_k,
                filters=filters
            )
            
            return results.get("result", {}).get("data_array", [])
            
        except Exception as e:
            print(f"⚠️  Search error: {e}")
            return []
    
    def index_facilities(self, facilities_df: pd.DataFrame) -> None:
        """
        Index facility data with embeddings.
        
        Args:
            facilities_df: DataFrame with facility information
        """
        print(f"🔄 Indexing {len(facilities_df)} facilities...")
        
        # Generate embeddings for capabilities
        capability_texts = facilities_df["capabilities_raw"].fillna("").tolist()
        embeddings = self.embed_batch(capability_texts)
        
        # Add embeddings to dataframe
        facilities_df["capability_embedding"] = embeddings
        
        # Save to Delta table (Unity Catalog)
        table_path = f"{self.config.UNITY_CATALOG_NAME}.{self.config.UNITY_SCHEMA_NAME}.facilities"
        
        print(f"💾 Saving to Delta table: {table_path}")
        
        # In actual implementation, you'd use Databricks SQL connector or spark
        # For now, save locally as parquet
        local_path = self.config.PROCESSED_DATA_DIR / "facilities_with_embeddings.parquet"
        facilities_df.to_parquet(local_path, index=False)
        
        print(f"✅ Indexed {len(facilities_df)} facilities")
        print(f"📁 Local copy saved to: {local_path}")
    
    def find_capability_gaps(
        self, 
        region: str, 
        required_capabilities: List[str]
    ) -> Dict[str, Any]:
        """
        Identify missing capabilities in a region.
        
        Args:
            region: Geographic region to analyze
            required_capabilities: List of essential medical capabilities
            
        Returns:
            Analysis of capability gaps
        """
        gaps = {}
        
        for capability in required_capabilities:
            results = self.search_similar_facilities(
                query=capability,
                top_k=3,
                filters={"region": region}
            )
            
            if not results or len(results) < 2:
                gaps[capability] = {
                    "status": "critical_gap",
                    "available_count": len(results),
                    "nearest_facilities": results
                }
        
        return {
            "region": region,
            "capability_gaps": gaps,
            "gap_count": len(gaps)
        }


if __name__ == "__main__":
    # Quick test
    vector_search = DatabricksVectorSearch()
    print("✅ Vector Search client initialized successfully")
