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
from utils.supabase_db import insert_metadata, get_metadata, insert_log, get_member, get_all_members, upsert_member, remove_member
from utils.embedding_utils import get_embedding
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
# 3. /fix_member: 멤버 DB 수정
# 4. /add_member: 멤버 DB 추가
# 5. /remove_member: 멤버 DB 삭제
# 6. {text}: 질문에 답변
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
                "`@AutoPaper /members` → Show member list that AutoPaper can tag\n"
                "`@AutoPaper /fix_member` → Fix your member profile in the database\n"
                "`@AutoPaper /add_member` → Add a new member to the database\n"
                "`@AutoPaper /remove_member` → Remove yourself from the member database\n"
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
    
    # === /fix_member, /add_member ===
    if command == "/fix_member" or command == "/add_member":
        # 안내 메시지 + 버튼 응답 (trigger modal)
        say(
            text="Please click the button below to open the form.",
            thread_ts=thread_ts,
            blocks=[
                {
                    "type": "actions",
                    "elements": [
                        {
                            "type": "button",
                            "action_id": "open_add_or_fix_modal",
                            "text": {"type": "plain_text", "text": "Click to open the form"},
                            "value": "/add_member" if command == "/add_member" else f"/fix_member {user_id}"
                        }
                    ]
                }
            ]
        )
        return

    # === /remove_member ===
    if command == "/remove_member":
        say(
            text="Are you sure you want to remove your profile from the AutoPaper member database?",
            thread_ts=thread_ts,
            blocks=[
                {
                    "type": "actions",
                    "elements": [
                        {
                            "type": "button",
                            "action_id": "confirm_remove_member",
                            "style": "danger",
                            "text": {"type": "plain_text", "text": "Yes, remove me"},
                            "value": user_id
                        },
                        {
                            "type": "button",
                            "action_id": "cancel_remove_member",
                            "text": {"type": "plain_text", "text": "No, keep me"},
                            "value": user_id
                        }
                    ]
                }
            ]
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

@app.action("open_add_or_fix_modal")
def handle_modal_button(ack, body, client, logger):
    ack()
    trigger_id = body["trigger_id"]
    command = body["actions"][0]["value"]  # "/add_member" or "/fix_member user_id"
    is_add = command.startswith("/add_member")

    if is_add:
        user_info = {"slack_id": "", "name": "", "keywords": "", "interests": "", "current_projects": ""}
    else:
        target_id = command.split(" ")[1]
        user_info = get_member(target_id) or {"slack_id": target_id, "name": "", "keywords": "", "interests": "", "current_projects": ""}

    for key in ["slack_id", "name", "keywords", "interests", "current_projects"]:
        val = user_info.get(key)
        if isinstance(val, list):
            user_info[key] = ", ".join(val)
        elif val is None:
            user_info[key] = ""

    modal_blocks = []

    if is_add:
        modal_blocks.append({
            "type": "input",
            "block_id": "slack_id",
            "element": {"type": "plain_text_input", "action_id": "input", "initial_value": user_info["slack_id"]},
            "label": {"type": "plain_text", "text": "Slack ID"}
        })
    else:
        modal_blocks.append({
            "type": "section",
            "text": {
                "type": "mrkdwn",
                "text": f"*Slack ID:* `{user_info['slack_id']}`"
            }
        })

    # 공통 입력 필드
    modal_blocks.extend([
        {
            "type": "input",
            "block_id": "name",
            "element": {"type": "plain_text_input", "action_id": "input", "initial_value": user_info["name"]},
            "label": {"type": "plain_text", "text": "Name"}
        },
        {
            "type": "input",
            "block_id": "keywords",
            "element": {"type": "plain_text_input", "action_id": "input", "initial_value": user_info["keywords"]},
            "label": {"type": "plain_text", "text": "Keywords (comma-separated)"}
        },
        {
            "type": "input",
            "block_id": "interests",
            "element": {"type": "plain_text_input", "action_id": "input", "initial_value": user_info["interests"]},
            "label": {"type": "plain_text", "text": "Interests"}
        },
        {
            "type": "input",
            "block_id": "current_projects",
            "element": {"type": "plain_text_input", "action_id": "input", "initial_value": user_info["current_projects"]},
            "label": {"type": "plain_text", "text": "Current Projects"}
        }
    ])

    modal_view = {
        "type": "modal",
        "callback_id": "submit_member_form",
        "title": {"type": "plain_text", "text": "AutoPaper Member"},
        "submit": {"type": "plain_text", "text": "Save"},
        "blocks": modal_blocks,
        "private_metadata": user_info["slack_id"]
    }

    client.views_open(trigger_id=trigger_id, view=modal_view)

@app.view("submit_member_form")
def handle_submission(ack, body, client, view, logger):
    ack()

    vals = view["state"]["values"]
    slack_id = vals["slack_id"]["input"]["value"] if "slack_id" in vals else view["private_metadata"]
    name = vals["name"]["input"]["value"]
    keywords = [kw.strip() for kw in vals["keywords"]["input"]["value"].split(",") if kw.strip()]
    interests = vals["interests"]["input"]["value"]
    current_projects = vals["current_projects"]["input"]["value"]

    embedding = {
        "keywords": get_embedding(" ".join(keywords)) if keywords else [],
        "interests": get_embedding(interests) if interests else [],
        "current_projects": get_embedding(current_projects) if current_projects else []
    }

    upsert_member(
        slack_id=slack_id,
        name=name,
        keywords=keywords,
        interests=interests,
        current_projects=current_projects,
        embedding=embedding
    )

    client.chat_postMessage(
        channel=body["user"]["id"],
        text=(
            f"✅ Member profile for <@{slack_id}> has been updated!\n"
            f"• *Keywords:* {', '.join(keywords)}\n"
            f"• *Interests:* {interests}\n"
            f"• *Projects:* {current_projects}"
        )
    )

@app.action("confirm_remove_member")
def handle_remove_member_action(ack, body, client, logger):
    ack()
    slack_id = body["actions"][0]["value"]

    success = remove_member(slack_id)

    if success:
        client.chat_postMessage(
            channel=body["user"]["id"],
            text=f"🗑️ <@{slack_id}>'s profile has been removed from the database."
        )
    else:
        client.chat_postMessage(
            channel=body["user"]["id"],
            text=f"⚠️ Failed to remove <@{slack_id}>. Please try again or contact admin."
        )

@app.action("cancel_remove_member")
def handle_cancel_member_action(ack, body, client, logger):
    ack()
    client.chat_postMessage(
        channel=body["user"]["id"],
        text="❎ Member removal cancelled."
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
