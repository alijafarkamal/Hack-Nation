"""
Configuration settings for the Bridging Medical Deserts project.
Loads environment variables and provides centralized config access.
"""
import os
from pathlib import Path
from typing import Optional
from dotenv import load_dotenv

# Load environment variables
load_dotenv()

class Config:
    """Central configuration for the application."""
    
    # Project paths
    PROJECT_ROOT = Path(__file__).parent.parent
    DATA_DIR = PROJECT_ROOT / "data"
    RAW_DATA_DIR = DATA_DIR / "raw" / "ghana"
    PROCESSED_DATA_DIR = DATA_DIR / "processed"
    
    # Databricks Configuration
    DATABRICKS_HOST: str = os.getenv("DATABRICKS_HOST", "")
    DATABRICKS_TOKEN: str = os.getenv("DATABRICKS_TOKEN", "")
    
    # Unity Catalog
    UNITY_CATALOG_NAME: str = os.getenv("UNITY_CATALOG_NAME", "main")
    UNITY_SCHEMA_NAME: str = os.getenv("UNITY_SCHEMA_NAME", "medical_deserts")
    
    # Vector Search
    VECTOR_SEARCH_ENDPOINT: str = os.getenv("VECTOR_SEARCH_ENDPOINT", "")
    VECTOR_INDEX_NAME: str = f"{UNITY_CATALOG_NAME}.{UNITY_SCHEMA_NAME}.facility_embeddings"
    
    # MLflow Configuration
    MLFLOW_TRACKING_URI: str = os.getenv("MLFLOW_TRACKING_URI", "databricks")
    MLFLOW_EXPERIMENT_NAME: str = os.getenv(
        "MLFLOW_EXPERIMENT_NAME", 
        "/Users/default/medical-deserts-experiment"
    )
    
    # Model Configuration
    DATABRICKS_MODEL_ENDPOINT: str = os.getenv(
        "DATABRICKS_MODEL_ENDPOINT", 
        "databricks-dbrx-instruct"
    )
    EMBEDDING_MODEL: str = os.getenv(
        "EMBEDDING_MODEL", 
        "sentence-transformers/all-MiniLM-L6-v2"
    )
    
    # OpenAI (if using directly)
    OPENAI_API_KEY: Optional[str] = os.getenv("OPENAI_API_KEY")
    
    # Agent Configuration
    MAX_ITERATIONS: int = 5
    CONFIDENCE_THRESHOLD: float = 0.7
    MEDICAL_DESERT_RADIUS_KM: float = 50.0
    
    @classmethod
    def validate(cls) -> bool:
        """Validate that required configurations are set."""
        required = [
            ("DATABRICKS_HOST", cls.DATABRICKS_HOST),
            ("DATABRICKS_TOKEN", cls.DATABRICKS_TOKEN),
        ]
        
        missing = [name for name, value in required if not value]
        
        if missing:
            print(f"❌ Missing required configuration: {', '.join(missing)}")
            print(f"💡 Please set these in your .env file or environment variables")
            return False
        
        print("✅ Configuration validated successfully")
        return True

# Create directories if they don't exist
Config.RAW_DATA_DIR.mkdir(parents=True, exist_ok=True)
Config.PROCESSED_DATA_DIR.mkdir(parents=True, exist_ok=True)
