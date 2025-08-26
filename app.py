from slack_bolt import App
from slack_bolt.adapter.flask import SlackRequestHandler
from flask import Flask, request
from dotenv import load_dotenv
import os
import requests
import re
from subprocess import run
import time

# === Custom utility modules ===
from utils.pdf_utils import extract_text_from_pdf
from utils.summarizer import summarize_text, extract_keywords
from utils.interest_matcher import match_top_n_members, get_reason_for_tagging
from utils.link_utils import process_link_download
from utils.path_utils import get_pdf_path_from_thread, get_thread_hash
from utils.supabase_db import insert_metadata, get_metadata, insert_log, get_all_members
from utils.qna import answer_question
from utils.user_info import get_user_info

load_dotenv()

TEST = True

# === Slack app setup ===
app = App(token=os.getenv("SLACK_BOT_TOKEN"), signing_secret=os.getenv("SLACK_SIGNING_SECRET"))
flask_app = Flask(__name__)
handler = SlackRequestHandler(app)

# === 논문 링크 감지 ===
@app.event("message")
def handle_message(event, say, client, logger):
    logger.info(event)

    text = event.get("text", "")
    thread_ts = event["ts"]
    channel_id = event["channel"]
    user_id = event.get("user") or event.get("message", {}).get("user")

    thread_hash = get_thread_hash(thread_ts)
    pdf_path = get_pdf_path_from_thread(thread_ts)

    # 링크로부터 다운로드
    success, source_link, filename = process_link_download(text, pdf_path)
    if success:
        insert_metadata(thread_hash, {
            "user_id": user_id,
            "channel_id": channel_id,
            "timestamp": thread_ts,
            "filename": filename or os.path.basename(pdf_path), # e.g., 2508.00143.pdf
            "source": source_link # e.g., https://arxiv.org/abs/2508.00143
        })

        text = extract_text_from_pdf(pdf_path)
        post_summary_reply(client, channel_id, thread_ts, text, user_id)
        return

# === 요약 결과 전송 ===
def post_summary_reply(client, channel, thread_ts, text, user_id):
    client.chat_postMessage(
        channel=channel,
        user=user_id,
        thread_ts=thread_ts,
        text="Processing your document and generating response..."
    )

    summary = summarize_text(text)
    keywords = extract_keywords(text) # comma separated list of keywords
    keyword_tags = ' '.join([f"#{kw.replace(' ', '_')}" for kw in keywords])

    matched_users, sim_dict = match_top_n_members(summary, top_n=3, return_similarities=True, threshold=0.5, test=TEST)
    member_db = {m["slack_id"]: m for m in get_all_members()}

    user_reasons = []
    for uid in matched_users:
        reason = get_reason_for_tagging(uid, summary, test=TEST, member_db=member_db)
        user_reasons.append(f"• <@{uid}>: {reason}")

    summary_text = f"*[AutoPaper Summary]*\n{summary}"

    client.chat_postMessage(
        channel=channel,
        thread_ts=thread_ts,
        text=f"{summary_text}",
        blocks=[
            {"type": "section", "text": {"type": "mrkdwn", "text": summary_text}},
            {
                "type": "context",
                "elements": [
                    {"type": "mrkdwn", "text": ":label: Keywords:"},
                ] + [{"type": "mrkdwn", "text": keyword_tags}],
            },
            {
                "type": "context",
                "elements": [
                    {"type": "mrkdwn", "text": ":bust_in_silhouette: May be relevant to:"},
                ] + [{"type": "mrkdwn", "text": user_reason} for user_reason in user_reasons]
            },
        ]
    )

# === @autopaper 태그 시 ===
# 1. /help: 도움말 안내
# 2. /members: 멤버 목록 안내
# 3. {text}: 질문에 답변
@app.event("app_mention")
def handle_mention(event, say, client, logger):
    thread_ts = event.get("thread_ts")
    channel_id = event["channel"]
    user_id = event.get("user")
    full_text = event.get("text", "").strip()

    if not thread_ts:
        say("Please reply to a specific thread to ask a question.")
        return

    thread_hash = get_thread_hash(thread_ts)

    # === 멘션 제거 ===
    bot_user_id = client.auth_test()["user_id"] # 봇 user ID
    mention_pattern = rf"<@{bot_user_id}>"
    command = re.sub(mention_pattern, "", full_text).strip().lower()

    # === /help ===
    if command == "/help":
        say(
            text=(
                "*🤖 AutoPaper Help*\n"
                "`@AutoPaper [question]` → Ask a question about the paper\n"
                "`@AutoPaper /help` → Show this help message\n"
                "`@AutoPaper /members` → Show member list that AutoPaper can tag\n\n"
            ),
            thread_ts=thread_ts
        )
        return
    
    # === /members ===
    if command == "/members":
        member_db = {m["slack_id"]: m for m in get_all_members()}
        formatted = "\t".join(
            [f"{get_user_info(uid)["display_name"] if get_user_info(uid)["display_name"] else get_user_info(uid)["name"]}" for uid, profile in member_db.items()]
        )
        say(
            text=f"*🧑‍🔬 AutoPaper Members*\n{formatted}",
            thread_ts=thread_ts
        )
        return

    # === Normal QA (default) ===
    metadata = get_metadata(thread_hash)
    if not metadata:
        say("Cannot find metadata for this thread. Please ensure the thread has a valid PDF or link.")
        return

    pdf_path = get_pdf_path_from_thread(thread_ts)
    if not os.path.exists(pdf_path):
        # PDF가 없으면 다시 다운로드 시도
        if metadata["source"].startswith("http"):
            success, _, _ = process_link_download(metadata["source"], pdf_path)
            if not success:
                say("I cannot bring the PDF right now. Please ensure the link is valid or upload the PDF directly.")
                return
        else:
            say("PDF file not found. Please ensure it was uploaded or linked correctly.")
            return

    context_text = extract_text_from_pdf(pdf_path)
    answer = answer_question(context_text, command, thread_hash, max_history=10)

    # 질문/답변 로그 저장
    timestamp = time.time()
    insert_log(thread_hash, "user", command, user_id=event.get("user"), timestamp=timestamp)
    insert_log(thread_hash, "assistant", answer, timestamp=timestamp + 0.001)

    say(
        text=f"*Q: {command}*\n*A:* {answer}",
        thread_ts=thread_ts
    )

# === 기타 이벤트 무시 ===
@app.event("file_shared")
def handle_file_shared_events(body, logger):
    logger.info("file_shared 이벤트는 무시함. 링크만 처리됨.")

# === 이벤트 핸들러 ===
@flask_app.route("/slack/events", methods=["POST"])
def slack_events():
    if request.headers.get("Content-Type") == "application/json":
        payload = request.get_json()
        if "challenge" in payload:
            return payload["challenge"], 200
    return handler.handle(request)

# === temp 정리 트리거 (선택사항) ===
@flask_app.route("/cleanup", methods=["POST"])
def trigger_cleanup():
    run(["python", "cleanup_temp.py"])
    return "Cleanup triggered", 200

if __name__ == "__main__":
    flask_app.run(port=3000)
