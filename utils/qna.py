import os
import openai
from dotenv import load_dotenv

load_dotenv()
client = openai.OpenAI(api_key=os.getenv("OPENAI_API_KEY"))

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
