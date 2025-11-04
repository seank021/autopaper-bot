import os
import json
import sys
import openai
from dotenv import load_dotenv
load_dotenv()
client = openai.OpenAI(api_key=os.getenv("OPENAI_API_KEY"))
sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))
from utils.embedding_utils import get_embedding
from utils.supabase_db import upsert_member
from member.member_db import MEMBER_DB

def main():
    dir = "user_embeddings"
    os.makedirs(dir, exist_ok=True)

    for slack_id, info in MEMBER_DB.items():
        print(f"[→] Processing {slack_id} ({info['name']})")

        # 임베딩 생성
        embedding = {
            "keywords": get_embedding(" ".join(info["keywords"])),
            "interests": get_embedding(info["interests"]),
        }

        # 로컬 저장 (선택적)
        with open(f"{dir}/{slack_id}.json", "w") as f:
            json.dump(embedding, f)

        # Supabase에 삽입
        try:
            upsert_member(
                slack_id=slack_id,
                name=info["name"],
                keywords=info["keywords"],
                interests=info["interests"],
                embedding=embedding
            )
            print(f"[✓] Inserted {slack_id}")
        except Exception as e:
            print(f"[x] Failed to insert {slack_id}: {e}")

if __name__ == "__main__":
    main()
