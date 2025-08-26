import os
from slack_sdk import WebClient
from dotenv import load_dotenv

load_dotenv()
client = WebClient(token=os.getenv("SLACK_BOT_TOKEN"))

def get_user_info(user_id):
    try:
        response = client.users_info(user=user_id)
        user = response["user"]
        return {
            "name": user["real_name"],
            "display_name": user["profile"].get("display_name"),
            "mention": f"<@{user['id']}>"
        }
    except Exception as e:
        print("Error fetching user info:", e)
        return None
    
TEST_USER_ID = "U090X2M5P8B"

if __name__ == "__main__":
    user_info = get_user_info(TEST_USER_ID)
    if user_info:
        print(user_info)
    else:
        print("Failed to retrieve user info.")
