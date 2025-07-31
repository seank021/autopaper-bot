from slack_bolt import App
from slack_bolt.adapter.flask import SlackRequestHandler
from flask import Flask, request, make_response
from utils.pdf_utils import extract_text_from_pdf
from utils.summarizer import summarize_text
from utils.interest_matcher import match_members
import os
from dotenv import load_dotenv
import requests

# 환경 변수 불러오기
load_dotenv()

app = App(token=os.getenv("SLACK_BOT_TOKEN"), signing_secret=os.getenv("SLACK_SIGNING_SECRET"))
flask_app = Flask(__name__)
handler = SlackRequestHandler(app)

# 파일 업로드 메시지 처리
@app.event("message")
def handle_file_share(event, say, client, logger):
    logger.info("📥 message 이벤트 감지됨!")
    logger.info(event)

    if event.get("subtype") != "file_share":
        return

    logger.info("📎 file_share 이벤트 감지됨!")

    file_info = event["files"][0]
    if file_info["filetype"] != "pdf":
        logger.info("❌ PDF 아님")
        return

    logger.info(f"📄 PDF 감지: {file_info['name']}")

    pdf_url = file_info["url_private_download"]
    headers = {"Authorization": f"Bearer {os.getenv('SLACK_BOT_TOKEN')}"}
    response = requests.get(pdf_url, headers=headers)

    os.makedirs("temp", exist_ok=True)
    with open("temp/temp.pdf", "wb") as f:
        f.write(response.content)

    text = extract_text_from_pdf("temp/temp.pdf")
    summary = summarize_text(text)

    # 사용자 태그 처리
    user_ids = match_members(summary)
    user_mentions = ' '.join([f"<@{uid}>" for uid in user_ids])

    logger.info(f"🔎 매칭된 유저: {user_mentions}")

    # 메시지 작성
    summary_text = f"*[AutoPaper 요약]*\n{summary}"

    client.chat_postMessage(
        channel=event["channel"],
        thread_ts=event["ts"],
        text=summary_text,  # fallback
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

# file_shared 이벤트 무시
@app.event("file_shared")
def handle_file_shared_events(body, logger):
    logger.info("📦 file_shared 이벤트 무시 (처리 안 함)")

# 슬랙 이벤트 수신 엔드포인트
@flask_app.route("/slack/events", methods=["POST"])
def slack_events():
    payload = request.get_json()

    # 👉 challenge 응답 처리
    if payload.get("type") == "url_verification":
        return make_response(payload.get("challenge"), 200, {"content_type": "text/plain"})

    return handler.handle(request)

if __name__ == "__main__":
    flask_app.run(port=3000)
