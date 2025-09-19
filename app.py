from slack_bolt import App
from slack_bolt.adapter.flask import SlackRequestHandler
from flask import Flask, request
from dotenv import load_dotenv
import os
import requests
import re
from subprocess import run
import time
from slack_sdk.errors import SlackApiError

# === Custom utility modules ===
from utils.pdf_utils import extract_text_from_pdf
from utils.summarizer import summarize_text, extract_keywords
from utils.member_tagger import match_top_n_members, get_reason_for_tagging
from utils.link_utils import process_link_download
from utils.path_utils import get_pdf_path_from_thread, get_thread_hash
from utils.supabase_db import insert_metadata, get_metadata, insert_log, get_member, get_all_members, upsert_member, remove_member
from utils.embedding_utils import get_embedding
from utils.qna import answer_question
from utils.user_info import get_user_info

load_dotenv()

# === Slack app setup ===
app = App(token=os.getenv("SLACK_BOT_TOKEN"), signing_secret=os.getenv("SLACK_SIGNING_SECRET"))
flask_app = Flask(__name__)
handler = SlackRequestHandler(app)

# === Helpers ===
BOT_USER_ID = None
MGMT_SLASHES = {"/add_member", "/fix_member", "/remove_member", "/members"}

def get_bot_user_id(client):
    global BOT_USER_ID
    if not BOT_USER_ID:
        BOT_USER_ID = client.auth_test()["user_id"]
    return BOT_USER_ID

def open_dm(client, user_id):
    res = client.conversations_open(users=user_id)
    return res["channel"]["id"]

def post_dm(client, user_id, text=None, blocks=None, prefer_channel=None):
    # 1) 현재 채널이 DM이면 그냥 거기로 보내기
    if prefer_channel and is_dm_channel(client, prefer_channel):
        client.chat_postMessage(channel=prefer_channel, text=text or "", blocks=blocks or [])
        return prefer_channel

    # 2) DM 열기(권한/정책 필요). 실패시 None
    try:
        res = client.conversations_open(users=user_id)
        dm = res["channel"]["id"]
        client.chat_postMessage(channel=dm, text=text or "", blocks=blocks or [])
        return dm
    except SlackApiError as e:
        # missing_scope / not_allowed_to_dm_user 같은 케이스
        return None

def is_dm_channel(client, channel_id):
    return isinstance(channel_id, str) and channel_id.startswith("D")

def contains_member_mgmt_command(text: str) -> bool:
    if not text:
        return False
    lowered = text.strip().lower()
    return lowered in MGMT_SLASHES

def dm_entry_blocks():
    return [{
        "type": "actions",
        "elements": [
            { "type": "button", "action_id": "dm_members", "text": {"type": "plain_text", "text": "Member List"}, "value": "members" },
            { "type": "button", "action_id": "dm_add_member", "text": {"type": "plain_text", "text": "Add a new member"}, "value": "add" },
            { "type": "button", "action_id": "dm_fix_member", "text": {"type": "plain_text", "text": "Fix my profile"}, "value": "fix" },
            { "type": "button", "action_id": "dm_remove_member", "text": {"type": "plain_text", "text": "Remove my profile"}, "value": "remove" }
        ]
    }]

def ensure_dm_for_mgmt(client, user_id, thread_ts=None, notice_in_channel=None):
    """채널에선 에페메럴로 공지 + DM 안내/버튼 발송"""
    if notice_in_channel and not is_dm_channel(client, notice_in_channel):
        client.chat_postEphemeral(
            channel=notice_in_channel,
            user=user_id,
            thread_ts=thread_ts,
            text="Administration commands are handled in DM. I’ve sent you a DM to continue!"
        )
    post_dm(
        client, user_id,
        text=(
            "Hi! 👋\n"
            "AutoPaper member management only supports **slash commands**:\n"
            "• `/members`  • `/add_member`  • `/fix_member`  • `/remove_member`\n\n"
            "Or use the buttons below:"
        ),
        blocks=dm_entry_blocks(),
        prefer_channel=notice_in_channel
    )

def render_member_list():
    members = get_all_members() or []
    if not members:
        return "No members found in the database."

    names = []
    for m in members:
        if not isinstance(m, dict):
            continue
        uid = m.get("slack_id")
        ui = get_user_info(uid) or {}
        display_name = ui.get("display_name")
        real_name = ui.get("name")
        names.append(display_name or real_name or str(uid))

    return "\t".join(names) if names else "No members found in the database."

# === 논문 링크 감지 ===
@app.event("message")
def handle_message(event, say, client, logger):
    logger.info(event)

    # Bot/self messages skip
    if event.get("bot_id") or event.get("subtype") in {"bot_message", "message_changed"}:
        return

    text = event.get("text", "")
    if not text:
        return
    
    channel_id = event["channel"]
    user_id = event.get("user") or event.get("message", {}).get("user")
    thread_ts = event.get("thread_ts") or event.get("ts")

    if contains_member_mgmt_command(text):
        ensure_dm_for_mgmt(client, user_id, thread_ts=thread_ts, notice_in_channel=channel_id)
        return

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
        extracted = extract_text_from_pdf(pdf_path)
        post_summary_reply(client, channel_id, thread_ts, extracted)
        return

# === 요약 결과 전송 ===
def post_summary_reply(client, channel, thread_ts, text):
    client.chat_postMessage(
        channel=channel,
        thread_ts=thread_ts,
        text="Processing your document and generating response..."
    )
    summary = summarize_text(text)
    keywords = extract_keywords(text) # comma separated list of keywords
    keyword_tags = ' '.join([f"#{kw.replace(' ', '_')}" for kw in keywords])

    matched_users, sim_dict = match_top_n_members(summary, top_n=3, return_similarities=True, threshold=0.5)
    member_db = {m["slack_id"]: m for m in get_all_members()}

    user_reasons = []
    for uid in matched_users:
        reason = get_reason_for_tagging(uid, summary, member_db=member_db)
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
                ] + (
                    [{"type": "mrkdwn", "text": user_reason} for user_reason in user_reasons]
                    if user_reasons
                    else [{"type": "mrkdwn", "text": "No relevant user found. Please mention manually."}]
                )
            },
        ]
    )

# === @autopaper 태그 시 ===
# @mention: 채널에서는 QA만 / 관리명령은 DM으로 유도
@app.event("app_mention")
def handle_mention(event, say, client, logger):
    thread_ts = event.get("thread_ts") or event.get("ts")
    channel_id = event["channel"]
    user_id = event.get("user")
    full_text = event.get("text", "").strip()

    # 멘션 제거 -> 실제 질문/명령만 남김
    bot_user_id = get_bot_user_id(client)
    command = re.sub(rf"<@{bot_user_id}>", "", full_text).strip()

    if contains_member_mgmt_command(command):
        ensure_dm_for_mgmt(client, user_id, thread_ts=thread_ts, notice_in_channel=channel_id)
        return
    
    # === Normal QA ===
    thread_hash = get_thread_hash(thread_ts)
    metadata = get_metadata(thread_hash)
    if not metadata:
        say("Cannot find metadata for this thread. Please ensure the thread has a valid PDF or link.", thread_ts=thread_ts)
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

    say(text=f"*Q: {command}*\n*A:* {answer}", thread_ts=thread_ts)

# === Actions: 채널 → DM 이동 버튼 ===
@app.action("goto_dm_for_mgmt")
def handle_goto_dm(ack, body, client, logger):
    ack()
    user_id = body["user"]["id"]
    ensure_dm_for_mgmt(client, user_id)

# === DM 내 버튼 액션 (add/fix/remove/members) ===
@app.action("dm_add_member")
def dm_add_member_action(ack, body, client, logger):
    ack()
    user_id = body["user"]["id"]
    open_add_or_fix_modal(client, trigger_id=body["trigger_id"], user_id=user_id, is_add=True)

@app.action("dm_fix_member")
def dm_fix_member_action(ack, body, client, logger):
    ack()
    user_id = body["user"]["id"]
    open_add_or_fix_modal(client, trigger_id=body["trigger_id"], user_id=user_id, is_add=False)

@app.action("dm_remove_member")
def dm_remove_member_action(ack, body, client, logger):
    ack()
    user_id = body["user"]["id"]
    channel_id = body.get("container", {}).get("channel_id") or body.get("channel", {}).get("id")
    ask_remove_confirmation(client, user_id, prefer_channel=channel_id)

@app.action("dm_members")
def dm_members_action(ack, body, client, logger):
    ack()
    user_id = body["user"]["id"]
    channel_id = body.get("container", {}).get("channel_id") or body.get("channel", {}).get("id")
    post_dm(client, user_id, text="*🧑‍🔬 AutoPaper Members*\n" + render_member_list(), prefer_channel=channel_id)

# === Slash Commands ===
@app.command("/add_member")
def slash_add(ack, body, client, logger):
    user_id = body["user_id"]
    channel_id = body.get("channel_id")
    in_dm = is_dm_channel(client, channel_id)
    ack() if in_dm else ack("Proceeding in DM!")
    post_dm(client, user_id,
        text="Adding a new member. Please click the button below to open the form.",
        blocks=[{"type":"actions","elements":[{"type":"button","action_id":"dm_add_member","text":{"type":"plain_text","text":"Form: Add the member"},"value":"add"}]}],
        prefer_channel=channel_id
    )
    
@app.command("/fix_member")
def slash_fix(ack, body, client, logger):
    user_id = body["user_id"]
    channel_id = body.get("channel_id")
    in_dm = is_dm_channel(client, channel_id)
    ack() if in_dm else ack("Proceeding in DM!")
    post_dm(client, user_id,
        text="Fixing your profile. Please click the button below to open the form.",
        blocks=[{"type":"actions","elements":[{"type":"button","action_id":"dm_fix_member","text":{"type":"plain_text","text":"Form: Fix yourself"},"value":"fix"}]}],
        prefer_channel=channel_id
    )

@app.command("/remove_member")
def slash_remove(ack, body, client, logger):
    user_id = body["user_id"]
    channel_id = body.get("channel_id")
    in_dm = is_dm_channel(client, channel_id)
    ack() if in_dm else ack("Proceeding in DM!")
    ask_remove_confirmation(client, user_id, prefer_channel=channel_id)

@app.command("/members")
def slash_members(ack, body, client, logger):
    user_id = body["user_id"]
    channel_id = body.get("channel_id")
    in_dm = is_dm_channel(client, channel_id)
    ack() if in_dm else ack("Proceeding in DM!")
    post_dm(client, user_id,
        text="*🧑‍🔬 AutoPaper Members*\n" + render_member_list(),
        prefer_channel=channel_id
    )

def help_text():
    return (
        "*🤖 AutoPaper Help*\n"
        "• `@AutoPaper [question]` → Ask a question about the paper (in thread)\n"
        "• `/members` → Show member list\n"
        "• `/add_member` → Add a new member\n"
        "• `/fix_member` → Fix my profile\n"
        "• `/remove_member` → Remove my profile\n"
        "• `/autopaper_help` → Show this help message\n\n"
        "(All member management commands are handled in DM.)"
    )

@app.command("/autopaper_help")
def slash_help(ack, body, client, logger):
    user_id = body["user_id"]
    channel_id = body.get("channel_id")
    in_dm = is_dm_channel(client, channel_id)
    ack() if in_dm else ack("Proceeding in DM!")
    post_dm(client, user_id, text=help_text(), prefer_channel=channel_id)

# === 멤버 추가/수정 모달 및 제출 처리 ===
def open_add_or_fix_modal(client, trigger_id, user_id, is_add: bool):
    if is_add:
        user_info = {"slack_id": "", "name": "", "keywords": "", "interests": ""}
    else:
        # 본인 프로필 수정: user_id 기준
        existing = get_member(user_id) or {"slack_id": user_id, "name": "", "keywords": "", "interests": ""}
        user_info = existing

    # normalize for inputs
    for key in ["slack_id", "name", "keywords", "interests"]:
        val = user_info.get(key)
        if isinstance(val, list):
            user_info[key] = ", ".join(val)
        elif val is None:
            user_info[key] = ""

    blocks = []
    if is_add:
        blocks.append({
            "type": "input",
            "block_id": "slack_id",
            "element": {"type": "plain_text_input", "action_id": "input", "initial_value": user_info["slack_id"]},
            "label": {"type": "plain_text", "text": "Slack ID (e.g., U12345678)"}
        })
    else:
        blocks.append({"type":"section","text":{"type":"mrkdwn","text":f"*Slack ID:* `{user_info['slack_id']}`"}})

    blocks.extend([
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
            "label": {"type": "plain_text", "text": "Keywords (comma-separated, e.g., visualization, HCI, design)"}
        },
        {
            "type": "input",
            "block_id": "interests",
            "element": {"type": "plain_text_input", "action_id": "input", "initial_value": user_info["interests"]},
            "label": {"type": "plain_text", "text": "Interests (multi-line OK)"}
        }
    ])

    view = {
        "type": "modal",
        "callback_id": "submit_member_form",
        "title": {"type": "plain_text", "text": "AutoPaper Member"},
        "submit": {"type": "plain_text", "text": "Save"},
        "blocks": blocks,
        "private_metadata": (user_info["slack_id"] if not is_add else "") # fix 모드일때 저장
    }
    client.views_open(trigger_id=trigger_id, view=view)

def ask_remove_confirmation(client, user_id, prefer_channel=None):
    target = None
    if prefer_channel and is_dm_channel(client, prefer_channel):
        target = prefer_channel
    else:
        target = post_dm(client, user_id, text="", blocks=[], prefer_channel=None)  # DM 열기
    if not target:
        return  # DM 불가 시 조용히 종료하거나 채널 안내 추가 가능

    client.chat_postMessage(
        channel=target,
        text="Are you sure you want to remove your profile from the AutoPaper member database? This action cannot be undone.",
        blocks=[{
            "type": "actions",
            "elements": [
                {"type": "button","action_id": "confirm_remove_member","style": "danger","text": {"type": "plain_text", "text": "Yes, remove me"},"value": user_id},
                {"type": "button","action_id": "cancel_remove_member","text": {"type": "plain_text", "text": "No, keep me"},"value": user_id}
            ]
        }]
    )

# 모달 제출
@app.view("submit_member_form")
def handle_submission(ack, body, client, view, logger):
    ack()
    vals = view["state"]["values"]
    # add 모드면 slack_id input이 있고, fix 모드면 private_metadata에 들어있음
    slack_id = (vals["slack_id"]["input"]["value"].strip() if "slack_id" in vals else view["private_metadata"] or body["user"]["id"])
    name = vals["name"]["input"]["value"].strip()
    keywords = [kw.strip() for kw in vals["keywords"]["input"]["value"].split(",") if kw.strip()]
    interests = vals["interests"]["input"]["value"].strip()

    embedding = {
        "keywords": get_embedding(" ".join(keywords)) if keywords else [],
        "interests": get_embedding(interests) if interests else []
    }

    upsert_member(
        slack_id=slack_id,
        name=name,
        keywords=keywords,
        interests=interests,
        embedding=embedding
    )

    msg = "added" if "slack_id" in vals else "updated"
    client.chat_postMessage(
        channel=body["user"]["id"],
        text=(
            f"✅ Member profile for <@{slack_id}> has been {msg}!\n"
            f"• *Keywords:* {', '.join(keywords) if keywords else '(none)'}\n"
            f"• *Interests:* {interests or '(none)'}\n"
        )
    )

# 삭제 확인/취소
@app.action("confirm_remove_member")
def handle_remove_member_action(ack, body, client, logger):
    ack()
    slack_id = body["actions"][0]["value"]
    ok = remove_member(slack_id)
    client.chat_postMessage(
        channel=body["user"]["id"],
        text=("✅ Your profile has been removed from the AutoPaper member database." if ok else "⚠️ Failed to remove your profile. It may not exist.")
    )

@app.action("cancel_remove_member")
def handle_cancel_member_action(ack, body, client, logger):
    ack()
    client.chat_postMessage(channel=body["user"]["id"], text="❎ Removal cancelled. Your profile is safe!")

# === 기타 이벤트 무시 ===
@app.event("file_shared")
def handle_file_shared_events(body, logger):
    logger.info("file_shared event ignored. Only link is processed.")

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
