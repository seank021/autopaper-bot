from database import INTEREST_DB
from utils.openai_utils import classify_relevance

def match_members(summary_text):
    matched_user_ids = []

    for user_id, profile in INTEREST_DB.items():
        keywords = profile.get("keywords", [])
        interest_text = profile.get("interests", "")

        # === Step 1: Keyword match ===
        keyword_match = any(
            kw.lower() in summary_text.lower() for kw in keywords
        )

        # === Step 2: LLM-based semantic match ===
        llm_match = classify_relevance(summary_text, interest_text)

        # === Hybrid Match: Either is True ===
        if keyword_match or llm_match:
            matched_user_ids.append(user_id)

    return matched_user_ids
