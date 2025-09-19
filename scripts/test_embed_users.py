import sys
import os
import json
sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))
from utils.embedding_utils import get_embedding
from database.test_member import TEST_MEMBER_DB

os.makedirs("test_user_embeddings", exist_ok=True)

for user_id, info in TEST_MEMBER_DB.items():
    user_embedding = {}
    user_embedding["keywords"] = get_embedding(" ".join(info["keywords"]))
    user_embedding["interests"] = get_embedding(info["interests"])

    with open(f"test_user_embeddings/{user_id}.json", "w") as f:
        json.dump(user_embedding, f)

    print(f"[✓] Saved embedding for test user: {user_id}")
