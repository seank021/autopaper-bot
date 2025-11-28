########## Mamber Tagger based on LLM ##########
import os
import json
import sys
from openai import OpenAI
sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))
from utils.supabase_db import get_all_members

client = OpenAI(api_key=os.getenv("OPENAI_API_KEY"))

def match_top_n_members(
    summary_text,
    top_n=3,
    weights=None, # 인터페이스 유지용 (사용 안 함)
    return_similarities=False,
    threshold=0.6, # LLM 점수 기준 임계값
    exclude_ids=None,
):
    exclude_ids = set(exclude_ids or [])

    members = get_all_members()
    if not members:
        return ([], {}) if return_similarities else []

    # 유효한 멤버 정보 정리
    member_profiles = []
    valid_slack_ids = set()

    for m in members:
        slack_id = m.get("slack_id")
        if not slack_id:
            continue
        if slack_id in exclude_ids:
            continue

        valid_slack_ids.add(slack_id)
        member_profiles.append({
            "slack_id": slack_id,
            "name": m.get("name") or m.get("real_name") or "",
            "keywords": m.get("keywords", []),
            "interests": m.get("interests", ""),
        })

    if not member_profiles:
        return ([], {}) if return_similarities else []

    # LLM에게 넘길 멤버 리스트를 문자열로 정리
    member_desc_lines = []
    for profile in member_profiles:
        line = (
            f"- slack_id: {profile['slack_id']}\n"
            f"  name: {profile['name']}\n"
            f"  keywords: {', '.join(profile['keywords']) if profile['keywords'] else 'None'}\n"
            f"  interests: {profile['interests'] or 'None'}"
        )
        member_desc_lines.append(line)

    members_block = "\n\n".join(member_desc_lines)

    # LLM 프롬프트
    system_prompt = """
    You are an assistant for an HCI research lab.
    Your task is to select lab members who are most likely to be interested in a given paper
    and assign a relevance score to each selected member.

    You are given:
    1) A short summary of a research paper.
    2) A list of lab members with their slack_id, keywords and interests.

    Your goal is HIGH PRECISION:
    - It is BETTER to select fewer members than too many.
    - Only select members whose research interests are DIRECTLY related to the main topic of the paper.
    - Generic overlap like "LLM", "AI", or "reasoning" alone is NOT enough for a strong match.
    - Prefer members whose keywords and interests match the paper's SPECIFIC domain, modality, task, or method
      (e.g., education, evaluation, creativity support, video, multimodal, alignment, etc.).

    Scoring guideline (0.0 to 1.0):
    - 0.9–1.0: extremely strong and direct match
        (same domain + same type of task/method; clearly ideal reviewer/reader)
    - 0.7–0.89: strong match
        (clear overlap in domain OR method, but not perfect)
    - 0.5–0.69: moderate / borderline match
        (some overlap, but either domain or method is not well aligned)
    - 0.3–0.49: weak match
        (only generic AI/LLM overlap or very indirect connection; usually DO NOT select)
    - below 0.3: very weak or irrelevant (DO NOT select)

    Selection rules:
    - Choose up to N members who are clearly relevant to the paper.
    - If only 1 person looks clearly relevant, you may return just 1.
    - If relevance is weak for almost all members, return an empty list.
    - Do NOT "force" the list to have many members. Use low scores (<= 0.4) if unsure.

    Output format:
    - You MUST respond with a JSON object ONLY.
    - The JSON must have the following schema:
        {
            "members": [
                { "slack_id": "U123", "score": 0.92 },
                { "slack_id": "U456", "score": 0.81 }
            ]
        }
    - "members" must be a list.
    - Each "score" must be a number between 0.0 and 1.0.
    - Only use slack_ids that appear in the member list provided.
    - DO NOT make up or hallucinate new slack_ids.
    - DO NOT select any slack_id listed under "Excluded IDs".
    """.strip()

    excluded_block = ", ".join(sorted(exclude_ids)) if exclude_ids else "(none)"

    # Few-shot 예시 포함 프롬프트
    user_prompt = f"""
    Below is an example of how you should think:

    [Example]
    Paper Summary:
    "We design a system that helps teachers use LLMs in classrooms for formative feedback and
    metacognitive support. The system focuses on K-12 education and learning analytics."

    Members:
    - A: keywords: evaluation, reasoning; interests: evaluation of general LLM reasoning.
    - B: keywords: education, learning, metacognition; interests: AI in education and metacognition.
    - C: keywords: creativity, art; interests: creativity support tools for artists.

    Good output JSON:
    {{
        "members": [
            {{ "slack_id": "B", "score": 0.88 }}
        ]
    }}
    (Only B is selected. A and C are not selected because they are too generic or off-domain.)

    ----------------------------------------------
    Now do the real task.

    # Paper Summary
    {summary_text}

    # Members (valid candidates)
    {members_block}

    # Excluded IDs (must NOT select)
    {excluded_block}

    # Selection Specification
    - Maximum number of members to select: {top_n}
    - Only include members who are clearly and directly relevant to the paper.
    - If relevance is weak for almost all members, select at most 1 or return an empty list.

    Respond with JSON ONLY, following this exact schema:
    {{
        "members": [
            {{ "slack_id": "UXXXXXXX", "score": 0.85 }},
            {{ "slack_id": "UYYYYYYY", "score": 0.73 }}
        ]
    }}
    """.strip()

    max_retries = 3
    chosen_members = [] # list of (slack_id, score)

    for attempt in range(max_retries):
        try:
            response = client.chat.completions.create(
                model="gpt-4o",
                response_format={"type": "json_object"},
                messages=[
                    {"role": "system", "content": system_prompt},
                    {"role": "user", "content": user_prompt},
                ],
            )
            content = response.choices[0].message.content
            data = json.loads(content)

            members_field = data.get("members", [])
            if not isinstance(members_field, list):
                raise ValueError("members is not a list")

            tmp_list = []
            for item in members_field:
                if not isinstance(item, dict):
                    continue
                sid = item.get("slack_id")
                score = item.get("score")

                # slack_id 체크
                if not isinstance(sid, str):
                    continue
                sid = sid.strip()
                if sid not in valid_slack_ids:
                    continue

                # score 체크
                try:
                    score_val = float(score)
                except (TypeError, ValueError):
                    continue
                if not (0.0 <= score_val <= 1.0):
                    continue

                tmp_list.append((sid, score_val))

            if tmp_list:
                # score 기준으로 정렬 (내림차순)
                tmp_list.sort(key=lambda x: x[1], reverse=True)

                # threshold 이상인 것만, top_n까지
                filtered = [(sid, sc) for sid, sc in tmp_list if sc >= threshold][:top_n]

                # 아무도 threshold를 못 넘으면, 정말 제일 높은 사람도 0.6 이하라면 "관계가 약하다"로 보고 아무도 안 뽑기
                if not filtered:
                    # 가장 높은 점수가 0.5 이상이면 1명만 fallback으로 뽑고,
                    # 그마저도 낮으면 완전 빈 리스트 유지
                    best_sid, best_score = tmp_list[0]
                    if best_score >= 0.5:
                        filtered = [(best_sid, best_score)]

                chosen_members = filtered
                break
            # 아무것도 없으면 retry (최종적으로 없으면 빈 리스트)
        except Exception:
            if attempt == max_retries - 1:
                chosen_members = []
            continue

    top_users = [sid for sid, _ in chosen_members if sid not in exclude_ids]

    # similarity_scores: LLM이 준 score 그대로 반영, 선택 안 된 멤버는 0.0
    similarity_scores = {sid: 0.0 for sid in valid_slack_ids}
    for sid, sc in chosen_members:
        if sid in exclude_ids:
            continue
        similarity_scores[sid] = round(float(sc), 4)

    if return_similarities:
        return top_users, similarity_scores
    return top_users


def get_reason_for_tagging(user_id, summary_text, member_db=None):
    if member_db is None:
        members = get_all_members()
        member_db = {m["slack_id"]: m for m in members if m.get("slack_id")}

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
