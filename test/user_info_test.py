import os
from slack_sdk import WebClient
from dotenv import load_dotenv

load_dotenv()
client = WebClient(token=os.getenv("SLACK_BOT_TOKEN"))

TEST_USER_ID = "U090X2M5P8B"

try:
    response = client.users_info(user=TEST_USER_ID)
    user = response["user"]
    print("유저 정보 조회 성공")
    print(f"이름: {user['real_name']}")
    print(f"디스플레이 이름: {user['profile'].get('display_name')}")
    print(f"멘션용 형식: <@{user['id']}>")
except Exception as e:
    print("유저 정보 조회 실패:", e)
