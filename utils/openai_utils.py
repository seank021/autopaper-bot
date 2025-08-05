import os
import openai
from dotenv import load_dotenv

load_dotenv()
client = openai.OpenAI(api_key=os.getenv("OPENAI_API_KEY"))

def classify_relevance(summary: str, keywords: str, interest_desc: str, curr_prjs: str) -> bool:
    prompt = (
        "You are an academic assistant. Based on the following paper summary and the user's interests, "
        "determine if this paper is likely to be of interest to the user. "
        "The users are from the HCI research community.\n\n"
        f"Paper Summary:\n{summary}\n\n"
        f"User Interests:\n{interest_desc}\n"
        f"User Current Projects:\n{curr_prjs}\n"
        f"User Keywords:\n{keywords}\n\n"
        "Answer only 'Yes' or 'No'."
    )

    try:
        response = client.chat.completions.create(
            model="gpt-4o",
            messages=[{"role": "user", "content": prompt}]
        )
        reply = response.choices[0].message.content.strip().lower()
        return "yes" in reply
    except Exception as e:
        print(f"[match_members error] {e}")
        return False

def answer_question(context: str, question: str) -> str:
    prompt = (
        "You are a helpful academic assistant. Answer the question based on the paper below.\n\n"
        f"Paper:\n{context}\n\n"
        f"Question:\n{question}"
    )
    try:
        response = client.chat.completions.create(
            model="gpt-4o",
            messages=[
                {"role": "user", "content": prompt}
            ]
        )
        return response.choices[0].message.content.strip()
    except Exception as e:
        print(f"[OpenAI Error] {e}")
        return "답변 생성 중 오류가 발생했습니다."
