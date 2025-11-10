import os
import sys
from pprint import pprint

# 프로젝트 루트 추가
sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))

from utils.supabase_db import get_all_members
from utils.member_tagger import match_top_n_members, get_reason_for_tagging
from utils.summarizer import summarize_for_matching, extract_keywords
from utils.pdf_utils import extract_text_from_pdf
from utils.link_utils import process_link_download


def pretty_member(m):
    return {
        "slack_id": m.get("slack_id"),
        "name": m.get("name"),
        "keywords": m.get("keywords"),
        "interests": m.get("interests"),
        "current_projects": m.get("current_projects"),
    }


def main():
    # 1) 테스트할 논문 링크 입력
    paper_link = input("Paper link (arXiv): ").strip()
    if not paper_link:
        print("❌ No link provided. Exiting.")
        return

    # 2) 임시 PDF 경로 설정 & 다운로드
    base_dir = os.path.abspath(os.path.join(os.path.dirname(__file__), ".."))
    temp_dir = os.path.join(base_dir, "temp_test")
    os.makedirs(temp_dir, exist_ok=True)
    pdf_path = os.path.join(temp_dir, "test_matcher.pdf")

    print(f"\n=== Downloading PDF to {pdf_path} ===")
    success, source_link, filename = process_link_download(paper_link, pdf_path)
    if not success:
        print(f"❌ Failed to download from link: {paper_link}")
        return

    print(f"✅ Downloaded from: {source_link}")
    if filename:
        print(f"Saved as: {filename}")

    # 3) PDF에서 텍스트 추출
    print("\n=== Extracting text from PDF ===")
    raw_text = extract_text_from_pdf(pdf_path)
    if not raw_text or raw_text.strip() == "":
        print("❌ Failed to extract text from PDF (empty text).")
        return

    # 4) matcher용 summary 만들기
    print("\n=== Generating matching summary ===")
    matching_summary = summarize_for_matching(raw_text)
    print("\n[Matching Summary]")
    print(matching_summary)

    # 5) 키워드 뽑기
    print("\n=== Extracting keywords ===")
    keywords = extract_keywords(raw_text)
    if not keywords:
        keywords = []
    elif isinstance(keywords, str):
        keywords = [kw.strip() for kw in keywords.split(",") if kw.strip()]
    print("[Keywords]", keywords)

    # 6) matcher에 넘길 input 구성
    tagger_input = matching_summary
    if keywords:
        tagger_input += "\n\nPaper Keywords: " + ", ".join(keywords)

    # 7) 멤버 DB 확인
    members = get_all_members() or []
    print(f"\n=== Members in DB: {len(members)} ===")
    # for m in members:
    #     pprint(pretty_member(m))
    if not members:
        print("⚠️ No members found. Add some via /add_member in Slack first.")
        return

    # 8) 매칭 실행
    print("\n=== Running match_top_n_members ===")
    top_users, sim_dict = match_top_n_members(
        tagger_input,
        top_n=3,
        return_similarities=True,
        threshold=0.5,
    )

    print("\n[Matched slack_ids]:", top_users)
    print("\n[All similarity scores (> 0 only)]:")
    for sid, sc in sim_dict.items():
        if sc > 0:
            print(f"  {sid}: {sc:.3f}")

    # 9) 이유까지 같이 보기
    print("\n=== Reasons for tagging ===")
    member_db = {m["slack_id"]: m for m in members if m.get("slack_id")}
    for uid in top_users:
        reason = get_reason_for_tagging(uid, matching_summary, member_db=member_db)
        print(f"- {uid}: {reason}")


if __name__ == "__main__":
    main()
