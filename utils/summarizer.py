import openai
import os
from dotenv import load_dotenv

load_dotenv()
client = openai.OpenAI(api_key=os.getenv("OPENAI_API_KEY"))

def summarize_text(text):
    text = text[:3000]  # 단순 토큰 자르기
    response = client.chat.completions.create(
        model="gpt-4o",
        messages=[
            {"role": "system", "content": "너는 논문을 잘 요약하는 AI야."},
            {"role": "user", "content": f"다음 논문을 5줄 이내로 요약해줘:\n{text}"}
        ]
    )
    return response.choices[0].message.content.strip()
