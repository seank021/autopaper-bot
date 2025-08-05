import sys
import os
import json
sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))

from utils.link_utils import process_link_download
from utils.pdf_utils import extract_text_from_pdf
from utils.summarizer import summarize_text
from utils.interest_matcher import match_top_n_members

PAPER_LINKS = [
    "https://arxiv.org/abs/2503.23315",
    "https://arxiv.org/abs/2506.23678",
    "https://arxiv.org/abs/2409.08937",
    "https://arxiv.org/abs/2507.01921",
    "https://arxiv.org/abs/2409.12538",
    "https://arxiv.org/abs/2507.13524",
    "https://arxiv.org/abs/2507.07935",
    "https://arxiv.org/abs/2507.22358",
    "https://arxiv.org/abs/2508.00723"
]

output_path = "test/paper_user_match_results.json"
os.makedirs("temp", exist_ok=True)

results = []

for link in PAPER_LINKS:
    thread_hash = link.split("/")[-1]
    pdf_path = f"temp/{thread_hash}.pdf"

    print(f"처리 중: {link}")
    success, _, _ = process_link_download(link, pdf_path)

    if not success:
        print("PDF 다운로드 실패")
        results.append({
            "paper": link,
            "summary": "",
            "matched_users": [],
            "similarities": {}
        })
        continue

    try:
        text = extract_text_from_pdf(pdf_path)
        summary = summarize_text(text)
        matched_users, sim_dict = match_top_n_members(summary, return_similarities=True)

        results.append({
            "paper": link,
            "summary": summary,
            "matched_users": matched_users,
            "similarities": sim_dict
        })

    except Exception as e:
        print(f"처리 중 오류 발생: {e}")
        results.append({
            "paper": link,
            "summary": "",
            "matched_users": [],
            "similarities": {}
        })

with open(output_path, "w") as f:
    json.dump(results, f, indent=4)

print(f"저장 완료: {output_path}")
