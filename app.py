from slack_bolt import App
from slack_bolt.adapter.flask import SlackRequestHandler
from flask import Flask, request
from utils.pdf_utils import extract_text_from_pdf
from utils.summarizer import summarize_text
from utils.interest_matcher import match_members
import os
from dotenv import load_dotenv
import requests

load_dotenv()

app = App(token=os.getenv("SLACK_BOT_TOKEN"), signing_secret=os.getenv("SLACK_SIGNING_SECRET"))
flask_app = Flask(__name__)
handler = SlackRequestHandler(app)

# Slack message event handler
@app.event("message")
def handle_file_share(event, say, client, logger):
    logger.info(event)

    if event.get("subtype") != "file_share":
        return

    file_info = event["files"][0]
    if file_info["filetype"] != "pdf":
        logger.info("PDF 형식이 아님")
        return

    logger.info(f"PDF 파일: {file_info['name']}")

    pdf_url = file_info["url_private_download"]
    headers = {"Authorization": f"Bearer {os.getenv('SLACK_BOT_TOKEN')}"}
    response = requests.get(pdf_url, headers=headers)

    os.makedirs("temp", exist_ok=True)
    with open("temp/temp.pdf", "wb") as f:
        f.write(response.content)

    text = extract_text_from_pdf("temp/temp.pdf")
    summary = summarize_text(text)

    # Tag related users
    user_ids = match_members(summary)
    user_mentions = ' '.join([f"<@{uid}>" for uid in user_ids])
    logger.info(f"매칭된 유저: {user_mentions}")

    # Bot message
    summary_text = f"*[AutoPaper 요약]*\n{summary}"

    client.chat_postMessage(
        channel=event["channel"],
        thread_ts=event["ts"],
        text=summary_text,
        blocks=[
            {
                "type": "section",
                "text": {
                    "type": "mrkdwn",
                    "text": summary_text
                }
            },
            {
                "type": "context",
                "elements": [
                    {
                        "type": "mrkdwn",
                        "text": f":bust_in_silhouette: 관련 있을 만한 사람: {user_mentions}"
                    }
                ]
            }
        ]
    )

# Ignore file_shared events since they are already handled by file_share
@app.event("file_shared")
def handle_file_shared_events(body, logger):
    logger.info("file_shared 이벤트는 따로 처리 안 함. (이미 file_share 이벤트에서 처리됨)")

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
