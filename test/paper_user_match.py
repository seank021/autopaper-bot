import sys
import os
import json
from sentence_transformers import CrossEncoder
sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))
from utils.link_utils import process_link_download
from utils.pdf_utils import extract_text_from_pdf
from utils.summarizer import summarize_text
from utils.embedding_utils import get_embedding, cosine_similarity

CE_MODEL_NAME = "cross-encoder/ms-marco-MiniLM-L-6-v2"
ce_model = CrossEncoder(CE_MODEL_NAME)

# Test DB versions (tmember1.json ~ tmember6.json)
TMEMBER_VERSIONS = [1, 2, 3, 4, 5, 6]

PAPER_LINKS = [
    "https://arxiv.org/abs/2503.23315",
    "https://arxiv.org/abs/2506.23678",
    "https://arxiv.org/abs/2409.08937",
    "https://arxiv.org/abs/2507.01921",
    "https://arxiv.org/abs/2507.13524",
    "https://arxiv.org/abs/2507.07935",
    "https://arxiv.org/abs/2507.22358",
    "https://arxiv.org/abs/2508.00723",
    "https://arxiv.org/abs/2406.12465",
    "https://arxiv.org/abs/2507.21071",
    "https://arxiv.org/abs/2508.13141",
    "https://arxiv.org/abs/2508.14395",
    "https://arxiv.org/abs/2508.14160",
    "https://arxiv.org/pdf/2509.08010",
    "https://arxiv.org/abs/2504.10445",
    "https://arxiv.org/abs/2509.13348"
]

os.makedirs("temp", exist_ok=True)
os.makedirs("test/results", exist_ok=True)

# -------------------------------
# Local match function (with rerank)
# -------------------------------
def compute_weighted_similarity(summary_vec, user_vecs, weights):
    weighted_sum = 0.0
    total_weight = 0.0
    for field, weight in weights.items():
        vec = user_vecs.get(field)
        if vec is not None:
            sim = cosine_similarity(summary_vec, vec)
            weighted_sum += weight * sim
            total_weight += weight
    return round(weighted_sum / total_weight, 4) if total_weight > 0 else 0.0

def local_match_top_n_members(
    summary_text, 
    member_db, 
    top_n=3, 
    weights=None, 
    return_similarities=False, 
    threshold=0.5,
    min_top_score=0.35
):
    if weights is None:
        weights = {"keywords": 0.3, "interests": 0.7}

    summary_vec = get_embedding(summary_text)
    similarity_scores = {}

    for slack_id, profile in member_db.items():
        embedding = profile.get("embedding", {})
        if not slack_id or not embedding:
            continue
        sim_score = compute_weighted_similarity(summary_vec, embedding, weights)
        similarity_scores[slack_id] = sim_score

    if not similarity_scores:
        return ([], {}) if return_similarities else []

    sorted_users = sorted(similarity_scores.items(), key=lambda x: x[1], reverse=True)
    top_users = [user_id for user_id, _ in sorted_users[:top_n]]

    # 첫 번째 유저 점수 확인
    if similarity_scores[top_users[0]] < min_top_score:
        return ([], similarity_scores) if return_similarities else []

    filtered_users = [top_users[0]] + [
        u for u in top_users[1:] if similarity_scores[u] >= threshold
    ]

    # CrossEncoder rerank
    pairs = []
    for uid in filtered_users:
        profile = member_db.get(uid, {})
        profile_text = f"Keywords: {', '.join(profile.get('keywords', []))} | Interests: {profile.get('interests', '')}"
        pairs.append((summary_text, profile_text))

    if pairs:
        scores = ce_model.predict(pairs)
        filtered_users = [uid for uid, _ in sorted(zip(filtered_users, scores), key=lambda x: x[1], reverse=True)][:top_n]

    return (filtered_users, similarity_scores) if return_similarities else filtered_users

# -------------------------------
# Test runner
# -------------------------------
def run_tests(weights=None, threshold=0.5, versions=None):
    if weights is None:
        weights = {"keywords": 0.3, "interests": 0.7}
    if versions is None:
        versions = TMEMBER_VERSIONS

    # weight string (e.g., w46 for 0.4:0.6)
    kw = int(weights.get("keywords", 0) * 10)
    it = int(weights.get("interests", 0) * 10)
    wtag = f"w{kw}{it}"
    ttag = f"t{int(threshold*10)}"

    for ver in versions:
        print(f"\n=== Testing TMEMBER{ver} (weights={weights}, threshold={threshold}) ===")
        results = []

        db_path = f"test/member_db_embedded/tmember{ver}.json"
        if not os.path.exists(db_path):
            print(f"[v{ver}] DB not found at {db_path}, skipping...")
            continue

        with open(db_path, "r", encoding="utf-8") as f:
            member_db = json.load(f)

        for link in PAPER_LINKS:
            thread_hash = link.split("/")[-1]
            pdf_path = f"temp/{thread_hash}.pdf"

            print(f"[v{ver}] processing: {link}")
            success, _, _ = process_link_download(link, pdf_path)

            if not success:
                results.append({"paper": link, "summary": "", "matched_users": [], "similarities": {}})
                continue

            try:
                text = extract_text_from_pdf(pdf_path)
                summary = summarize_text(text)

                matched_users, sim_dict = local_match_top_n_members(
                    summary, member_db, 
                    top_n=3, 
                    weights=weights, 
                    threshold=threshold, 
                    return_similarities=True
                )
                sim_dict = dict(sorted(sim_dict.items(), key=lambda item: item[1], reverse=True))

                results.append({
                    "paper": link,
                    "summary": summary,
                    "matched_users": matched_users,
                    "similarities": sim_dict
                })

            except Exception as e:
                print(f"Error processing paper: {e}")
                results.append({"paper": link, "summary": "", "matched_users": [], "similarities": {}})

        # Save to structured path
        out_dir = f"test/results/v{ver}"
        os.makedirs(out_dir, exist_ok=True)
        out_file = f"{wtag}_{ttag}.json"
        out_path = os.path.join(out_dir, out_file)

        with open(out_path, "w", encoding="utf-8") as f:
            json.dump(results, f, indent=4, ensure_ascii=False)

        print(f"[v{ver}] saved to: {out_path}")

if __name__ == "__main__":
    run_tests(weights={"keywords": 0.8, "interests": 0.2}, threshold=0.5, versions=[1,2,3,4,5])
    run_tests(weights={"keywords": 0.9, "interests": 0.1}, threshold=0.5, versions=[1,2,3,4,5])
    run_tests(weights={"keywords": 1.0, "interests": 0.0}, threshold=0.5)
    run_tests(weights={"keywords": 0.5, "interests": 0.5}, threshold=0.5)
