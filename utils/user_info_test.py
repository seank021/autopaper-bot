import os
from slack_sdk import WebClient
from dotenv import load_dotenv

# .env에서 토큰 로딩
load_dotenv()
client = WebClient(token=os.getenv("SLACK_BOT_TOKEN"))

# 테스트할 유저 ID
TEST_USER_ID = "U0410KJN2NR"  # 너 자신의 ID 넣어도 좋아!

try:
    response = client.users_info(user=TEST_USER_ID)
    user = response["user"]
    print("✅ 유저 정보 조회 성공!")
    print(f"이름: {user['real_name']}")
    print(f"디스플레이 이름: {user['profile'].get('display_name')}")
    print(f"멘션용 형식: <@{user['id']}>")
except Exception as e:
    print("❌ 유저 정보 조회 실패:", e)
