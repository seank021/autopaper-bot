import os
import sys
import numpy as np
import importlib.util
import json
import openai
from dotenv import load_dotenv
load_dotenv()
client = openai.OpenAI(api_key=os.getenv("OPENAI_API_KEY"))

def load_module_from_path(name, path):
    spec = importlib.util.spec_from_file_location(name, path)
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    return mod

def get_embedding(text: str) -> list:
    response = client.embeddings.create(
        model="text-embedding-3-large",
        input=text
    )
    return response.data[0].embedding

def cosine_similarity(a: list, b: list) -> float:
    a, b = np.array(a), np.array(b)
    return np.dot(a, b) / (np.linalg.norm(a) * np.linalg.norm(b))

def add_embeddings_to_db(db):
    updated_db = {}
    for slack_id, profile in db.items():
        keywords = profile.get("keywords", [])
        interests = profile.get("interests", "")

        keywords_text = " ".join(keywords)
        embedding_keywords = get_embedding(keywords_text) if keywords_text else None
        embedding_interests = get_embedding(interests) if interests else None

        profile["embedding"] = {
            "keywords": embedding_keywords,
            "interests": embedding_interests
        }
        updated_db[slack_id] = profile

    return updated_db

def main():
    member_db_dir = "member"
    os.makedirs(member_db_dir, exist_ok=True)

    # Save to JSON
    path = f"{member_db_dir}/member.py"
    mod = load_module_from_path("member_db", path)
    db = getattr(mod, "MEMBER_DB")

    print(f"Generating embeddings... ({len(db)} members)")
    updated_db = add_embeddings_to_db(db)
    out_path = f"{member_db_dir}/member_db_embedded.json"
    with open(out_path, "w") as f:
        json.dump(updated_db, f, indent=4, ensure_ascii=False)
    print(f"Saved to: {out_path}")

if __name__ == "__main__":
    main()
