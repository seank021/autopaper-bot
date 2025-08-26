import os
import json
import sys
sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))
from utils.embedding_utils import get_embedding
from utils.supabase_db import insert_member
from database.member import MEMBER_DB
from database.test_member import TEST_MEMBER_DB

TEST = True

def main():
    dir = "test_user_embeddings" if TEST else "user_embeddings"
    os.makedirs(dir, exist_ok=True)

    member_db = TEST_MEMBER_DB if TEST else MEMBER_DB

    for slack_id, info in member_db.items():
        print(f"[→] Processing {slack_id} ({info['name']})")

        # 임베딩 생성
        embedding = {
            "keywords": get_embedding(" ".join(info["keywords"])),
            "interests": get_embedding(info["interests"]),
            "current_projects": get_embedding(info["current_projects"]),
        }

        # 로컬 저장 (선택적)
        with open(f"{dir}/{slack_id}.json", "w") as f:
            json.dump(embedding, f)

        # Supabase에 삽입
        try:
            insert_member(
                slack_id=slack_id,
                name=info["name"],
                keywords=info["keywords"],
                interests=info["interests"],
                current_projects=info["current_projects"],
                embedding=embedding
            )
            print(f"[✓] Inserted {slack_id}")
        except Exception as e:
            print(f"[x] Failed to insert {slack_id}: {e}")

if __name__ == "__main__":
    main()
