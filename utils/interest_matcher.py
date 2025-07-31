from database import INTEREST_DB

def match_members(summary_text):
    matched_user_ids = []
    for user_id, interests in INTEREST_DB.items():
        if any(keyword.lower() in summary_text.lower() for keyword in interests):
            matched_user_ids.append(user_id)
    return matched_user_ids
