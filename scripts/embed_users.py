import os
import sys
import importlib.util
import json
import openai
sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))
from utils.embedding_utils import get_embedding

client = openai.OpenAI(api_key=os.getenv("OPENAI_API_KEY"))

def load_module_from_path(name, path):
    spec = importlib.util.spec_from_file_location(name, path)
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    return mod


def add_embeddings_to_db(db, version):
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
    member_db_dir = "test/member_db"
    output_dir = "test/member_db_embedded"
    os.makedirs(output_dir, exist_ok=True)

    versions = [1, 2, 3, 4, 5, 6]

    for ver in versions:
        path = f"{member_db_dir}/tmember{ver}.py"
        mod = load_module_from_path(f"tmember{ver}", path)
        db = getattr(mod, f"TMEMBER{ver}")

        print(f"[v{ver}] Generating embeddings... ({len(db)} members)")

        updated_db = add_embeddings_to_db(db, ver)

        # Save to JSON
        out_path = f"{output_dir}/tmember{ver}.json"
        with open(out_path, "w") as f:
            json.dump(updated_db, f, indent=4, ensure_ascii=False)

        print(f"[v{ver}] saved to: {out_path}")


if __name__ == "__main__":
    main()
