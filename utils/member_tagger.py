import os
import json
import sys
from openai import OpenAI
from dotenv import load_dotenv
# from sentence_transformers import CrossEncoder
sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))
from utils.embedding_utils import get_embedding, cosine_similarity
from utils.supabase_db import get_all_members

load_dotenv()
client = OpenAI(api_key=os.getenv("OPENAI_API_KEY"))

# _ce_model = None

# def get_ce_model():
#     global _ce_model
#     if _ce_model is None:
#         from sentence_transformers import CrossEncoder
#         _ce_model = CrossEncoder("cross-encoder/ms-marco-MiniLM-L-6-v2")
#     return _ce_model

# def rerank(pairs):
#     model = get_ce_model()
#     return model.predict(pairs)

# Helper function to compute weighted similarity
def compute_weighted_similarity(summary_vec, user_vecs, weights):
    weighted_sum, total_weight = 0.0, 0.0
    for field, weight in weights.items():
        if field in user_vecs:
            sim = cosine_similarity(summary_vec, user_vecs[field])
            weighted_sum += weight * sim
            total_weight += weight
    return round(weighted_sum / total_weight, 4) if total_weight > 0 else 0.0

# Match top N members based on summary text - Currently, it matches one top member
def match_top_n_members(summary_text, top_n=3, weights=None, return_similarities=False, threshold=0.5): # threshold set experimentally
    if weights is None:
        weights = {"keywords": 0.8, "interests": 0.2} # set experimentally

    summary_vec = get_embedding(summary_text)
    similarity_scores = {}

    members = get_all_members() # From Supabase

    for member in members:
        slack_id = member.get("slack_id")
        embedding = member.get("embedding", {}) # dict

        if not slack_id or not embedding:
            continue

        sim_score = compute_weighted_similarity(summary_vec, embedding, weights)
        similarity_scores[slack_id] = sim_score

    sorted_users = sorted(similarity_scores.items(), key=lambda x: x[1], reverse=True)    
    top_users = [user_id for user_id, _ in sorted_users[:top_n]]
    if not top_users:
        return ([], similarity_scores) if return_similarities else []
    if similarity_scores[top_users[0]] < 0.35:
        return ([], similarity_scores) if return_similarities else []
    top_users = [top_users[0]] + [user for user in top_users[1:] if similarity_scores[user] >= threshold]

    # Rerank with CrossEncoder
    # members_dict = {m["slack_id"]: m for m in members if "slack_id" in m}
    # pairs = []
    # for uid in top_users:
    #     profile = members_dict.get(uid, {})
    #     profile_text = f"Keywords: {', '.join(profile.get('keywords', []))} | Interests: {profile.get('interests', '')}"
    #     pairs.append((summary_text, profile_text))

    # if pairs:
    #     scores = rerank(pairs)
    #     top_users = [uid for uid, _ in sorted(zip(top_users, scores), key=lambda x: x[1], reverse=True)][:top_n]

    return (top_users, similarity_scores) if return_similarities else top_users

# Reason for tagging this user
def get_reason_for_tagging(user_id, summary_text, member_db=None):
    if user_id not in member_db:
        return "User not found in the database."
    
    profile = member_db[user_id]
    keywords = profile.get("keywords", [])
    interest_text = profile.get("interests", "")

    prompt = f"""
    You are an academic assistant for the field of HCI (Human-Computer Interaction) research. 
    Given a summary of a research paper and a user's research profile, explain why this user might be interested in the paper.
    Respond with a concise explanation (15 words) of why this user should be tagged to read the paper, based on their keywords and interests.

    # Paper Summary
    {summary_text}

    # User Keywords
    {', '.join(keywords)}

    # User Interests
    {interest_text}

    # Response:
    """.strip()

    try:
        response = client.chat.completions.create(
            model="gpt-4o-mini",
            messages=[{"role": "user", "content": prompt}]
        )
        return response.choices[0].message.content.strip()
    except Exception as e:
        return f"[Error generating reason] {e}"
