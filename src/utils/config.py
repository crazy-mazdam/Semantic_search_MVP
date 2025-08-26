import os
import yaml
from pathlib import Path
from dotenv import load_dotenv

# Load environment variables
env_path = Path(__file__).resolve().parents[2] / ".env"
if env_path.exists():
    load_dotenv(env_path)

# Default config path
config_path = Path(__file__).resolve().parents[2] / "config.yaml"

def load_config(path=config_path):
    with open(path, "r") as f:
        config = yaml.safe_load(f)
    return config

# Example: read API key and model name from env/config
def get_settings():
    cfg = load_config()
    return {
        "openai_api_key": os.getenv("OPENAI_API_KEY", ""),
        "embedding_model": cfg.get("embedding_model", "BAAI/bge-large-en-v1.5"),
        "reranker_model": cfg.get("reranker_model", "BAAI/bge-reranker-large"),
        "chunk_size": cfg.get("chunk_size", 1000),
        "chunk_overlap": cfg.get("chunk_overlap", 150),
        "top_k_dense": cfg.get("top_k_dense", 50),
        "top_k_bm25": cfg.get("top_k_bm25", 50),
    }

if __name__ == "__main__":
    print(get_settings())