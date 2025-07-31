from slack_bolt import App
from slack_bolt.adapter.flask import SlackRequestHandler
from flask import Flask, request
from utils.pdf_utils import extract_text_from_pdf
from utils.summarizer import summarize_text
from utils.interest_matcher import match_members
from utils.link_utils import download_pdf_from_link
import os
from dotenv import load_dotenv
import requests

# Load environment variables
load_dotenv()

app = App(token=os.getenv("SLACK_BOT_TOKEN"), signing_secret=os.getenv("SLACK_SIGNING_SECRET"))
flask_app = Flask(__name__)
handler = SlackRequestHandler(app)

# Message event handler
@app.event("message")
def handle_message(event, say, client, logger):
    logger.info(event)

    text = event.get("text", "")
    subtype = event.get("subtype")

    # ==================== 1. PDF upload ====================
    if subtype == "file_share":
        file_info = event["files"][0]
        if file_info["filetype"] != "pdf":
            logger.info("PDF 형식이 아님")
            return

        logger.info(f"PDF 감지: {file_info['name']}")

        pdf_url = file_info["url_private_download"]
        headers = {"Authorization": f"Bearer {os.getenv('SLACK_BOT_TOKEN')}"}
        response = requests.get(pdf_url, headers=headers)

        os.makedirs("temp", exist_ok=True)
        with open("temp/temp.pdf", "wb") as f:
            f.write(response.content)

        text = extract_text_from_pdf("temp/temp.pdf")
        post_summary_reply(client, event["channel"], event["ts"], text)
        return

    # ==================== 2. Paper link ====================
    if download_pdf_from_link(text):
        text = extract_text_from_pdf("temp/temp.pdf")
        post_summary_reply(client, event["channel"], event["ts"], text)
        return

# Summarize and post reply
def post_summary_reply(client, channel, thread_ts, text):
    summary = summarize_text(text)
    user_ids = match_members(summary)
    user_mentions = ' '.join([f"<@{uid}>" for uid in user_ids])
    summary_text = f"*[AutoPaper 요약]*\n{summary}"

    client.chat_postMessage(
        channel=channel,
        thread_ts=thread_ts,
        text=summary_text,
        blocks=[
            {
                "type": "section",
                "text": {"type": "mrkdwn", "text": summary_text}
            },
            {
                "type": "context",
                "elements": [
                    {"type": "mrkdwn", "text": f":bust_in_silhouette: 관련 있을 만한 사람: {user_mentions}"}
                ]
            }
        ]
    )

# Ignore file_shared events
@app.event("file_shared")
def handle_file_shared_events(body, logger):
    logger.info("file_shared 이벤트는 message 이벤트에서 처리하므로 무시함")

# Slack event endpoint
@flask_app.route("/slack/events", methods=["POST"])
def slack_events():
    if request.headers.get("Content-Type") == "application/json":
        payload = request.get_json()
        if "challenge" in payload:
            return payload["challenge"], 200
    return handler.handle(request)

if __name__ == "__main__":
    flask_app.run(port=3000)
