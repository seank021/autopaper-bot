import sys
import os
import json
sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))
from utils.embedding_utils import get_embedding
from database import INTEREST_DB

os.makedirs("user_embeddings", exist_ok=True)

for user_id, info in INTEREST_DB.items():
    user_embedding = {}
    user_embedding["keywords"] = get_embedding(" ".join(info["keywords"]))
    user_embedding["interests"] = get_embedding(info["interests"])
    user_embedding["current_projects"] = get_embedding(info["current_projects"])

    with open(f"user_embeddings/{user_id}.json", "w") as f:
        json.dump(user_embedding, f)

    print(f"[✓] Saved embedding for user: {user_id}")
