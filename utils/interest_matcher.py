import os
import json
import sys
from openai import OpenAI
from dotenv import load_dotenv
sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))
from utils.embedding_utils import get_embedding, cosine_similarity
from utils.supabase_db import get_all_members

load_dotenv()
client = OpenAI(api_key=os.getenv("OPENAI_API_KEY"))

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
def match_top_n_members(summary_text, top_n=3, weights=None, return_similarities=False, threshold=0.5, test=False):
    if weights is None:
        weights = {"keywords": 0.0, "interests": 0.5, "current_projects": 0.5}

    summary_vec = get_embedding(summary_text)
    similarity_scores = {}

    members = get_all_members() # From Supabase

    for member in members:
        slack_id = member.get("slack_id")
        embedding = member.get("embedding", {}) # dict with 'interests', 'current_projects', ...

        if not slack_id or not embedding:
            continue

        sim_score = compute_weighted_similarity(summary_vec, embedding, weights)
        similarity_scores[slack_id] = sim_score

    sorted_users = sorted(similarity_scores.items(), key=lambda x: x[1], reverse=True)
    top_users = [user_id for user_id, _ in sorted_users[:top_n]]
    # The top user is always included, and the other users are filtered by the threshold
    top_users = [top_users[0]] + [user for user in top_users[1:] if similarity_scores[user] >= threshold]

    return (top_users, similarity_scores) if return_similarities else top_users

# Reason for tagging this user
def get_reason_for_tagging(user_id, summary_text, test=False, member_db=None):
    if user_id not in member_db:
        return "User not found in the database."
    
    profile = member_db[user_id]
    interest_text = profile.get("interests", "")
    project_text = profile.get("current_projects", "")

    prompt = f"""
    You are an academic assistant. Given a summary of a research paper and a user's research profile, explain why this user might be interested in the paper.
    Respond with a concise explanation (20 words) of why this user should be tagged to read the paper, based on their interests or current projects.

    # Paper Summary
    {summary_text}

    # User Interests
    {interest_text}

    # User Current Projects
    {project_text}

    # Response:
    """.strip()

    try:
        response = client.chat.completions.create(
            model="gpt-4.1-nano",
            messages=[{"role": "user", "content": prompt}]
        )
        return response.choices[0].message.content.strip()
    except Exception as e:
        return f"[Error generating reason] {e}"
