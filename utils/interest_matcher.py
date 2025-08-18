import os
import json
from utils.embedding_utils import get_embedding, cosine_similarity

# Helper function to compute weighted similarity
def compute_weighted_similarity(summary_vec, user_vecs, weights):
    weighted_sum = 0.0
    total_weight = 0.0
    for field, weight in weights.items():
        if field in user_vecs:
            sim = cosine_similarity(summary_vec, user_vecs[field])
            weighted_sum += weight * sim
            total_weight += weight
    return round(weighted_sum / total_weight, 4) if total_weight > 0 else 0.0


# Match top N members based on summary text - Currently, it matches one top member
def match_top_n_members(summary_text, top_n=1, weights=None, return_similarities=False):
    if weights is None:
        weights = {"keywords": 0.0, "interests": 0.5, "current_projects": 0.5}

    summary_vec = get_embedding(summary_text)
    similarity_scores = {}

    for filename in os.listdir("user_embeddings"):
        if not filename.endswith(".json"):
            continue
        user_id = filename.replace(".json", "")
        with open(os.path.join("user_embeddings", filename)) as f:
            user_vecs = json.load(f)
        similarity_scores[user_id] = compute_weighted_similarity(summary_vec, user_vecs, weights)

    sorted_users = sorted(similarity_scores.items(), key=lambda x: x[1], reverse=True)
    top_users = [user_id for user_id, _ in sorted_users[:top_n]]

    return (top_users, similarity_scores) if return_similarities else top_users


# Match members by threshold
def match_members_by_threshold(summary_text, threshold=0.5, weights=None, return_similarities=False):
    if weights is None:
        weights = {"keywords": 0.0, "interests": 0.5, "current_projects": 0.5}

    summary_vec = get_embedding(summary_text)
    matched_user_ids = []
    similarities = {}

    for filename in os.listdir("user_embeddings"):
        if not filename.endswith(".json"):
            continue
        user_id = filename.replace(".json", "")
        with open(os.path.join("user_embeddings", filename)) as f:
            user_vecs = json.load(f)
        sim = compute_weighted_similarity(summary_vec, user_vecs, weights)
        similarities[user_id] = sim
        if sim >= threshold:
            matched_user_ids.append(user_id)

    return (matched_user_ids, similarities) if return_similarities else matched_user_ids


"""
from database import MEMBER_DB
import os
import openai
from dotenv import load_dotenv

load_dotenv()
client = openai.OpenAI(api_key=os.getenv("OPENAI_API_KEY"))

def classify_relevance(summary: str, keywords: str, interest_desc: str, curr_prjs: str) -> bool:
    prompt = (
        "You are an academic assistant. Based on the following paper summary and the user's interests, "
        "determine if this paper is likely to be of interest to the user. "
        "The users are from the HCI research community.\n\n"
        f"Paper Summary:\n{summary}\n\n"
        f"User Interests:\n{interest_desc}\n"
        f"User Current Projects:\n{curr_prjs}\n"
        f"User Keywords:\n{keywords}\n\n"
        "Answer only 'Yes' or 'No'."
    )

    try:
        response = client.chat.completions.create(
            model="gpt-4o",
            messages=[{"role": "user", "content": prompt}]
        )
        reply = response.choices[0].message.content.strip().lower()
        return "yes" in reply
    except Exception as e:
        print(f"[match_members error] {e}")
        return False

def match_members(summary_text):
    matched_user_ids = []

    for user_id, profile in MEMBER_DB.items():
        keywords = ", ".join(profile.get("keywords", []))
        interest_text = profile.get("interests", "")
        curr_prjs = profile.get("current_projects", "")

        # === Step 1: Keyword match ===
        # keyword_match = any(
        #     kw.lower() in summary_text.lower() for kw in keywords
        # )

        # === Step 2: LLM-based semantic match ===
        llm_match = classify_relevance(summary_text, keywords, interest_text, curr_prjs)

        # === Hybrid Match: Either is True ===
        if llm_match:
            matched_user_ids.append(user_id)

    return matched_user_ids
"""
