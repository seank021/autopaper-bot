from slack_bolt import App
from slack_bolt.adapter.flask import SlackRequestHandler
from flask import Flask, request
from dotenv import load_dotenv
import os
import requests
from subprocess import run
import time

# === Database ===
from database.member import MEMBER_DB
from database.test_member import TEST_MEMBER_DB

# === Custom utility modules ===
from utils.pdf_utils import extract_text_from_pdf
from utils.summarizer import summarize_text, extract_keywords
from utils.interest_matcher import match_top_n_members, get_reason_for_tagging
from utils.link_utils import process_link_download
from utils.path_utils import get_pdf_path_from_thread, get_thread_hash
from utils.supabase_db import insert_metadata, get_metadata, insert_log
from utils.qna import answer_question

load_dotenv()

TEST = False

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
    member_db = TEST_MEMBER_DB if TEST else MEMBER_DB

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

# === Q&A 핸들러 (@autopaper 태그 시) ===
@app.event("app_mention")
def handle_qa(event, say, client, logger):
    thread_ts = event.get("thread_ts")
    channel_id = event["channel"]
    user_question = event.get("text", "").strip()

    if not thread_ts:
        say("Please reply to a specific thread to ask a question.")
        return

    thread_hash = get_thread_hash(thread_ts)
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

    text = extract_text_from_pdf(pdf_path)
    answer = answer_question(text, user_question, thread_hash, max_history=10)

    # 질문/답변 로그 저장
    timestamp = time.time()
    insert_log(thread_hash, "user", user_question, user_id=event.get("user"), timestamp=timestamp)
    insert_log(thread_hash, "assistant", answer, timestamp=timestamp + 0.001)

    say(
        text=f"*Q: {user_question}*\n*A:* {answer}",
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
