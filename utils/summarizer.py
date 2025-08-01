import openai
import os
from dotenv import load_dotenv

load_dotenv()
client = openai.OpenAI(api_key=os.getenv("OPENAI_API_KEY"))

def summarize_text(text):
    text = text
    response = client.chat.completions.create(
        model="gpt-4.1-nano",
        messages=[
            {"role": "system", "content": "You are a helpful assistant that summarizes academic papers."},
            {"role": "user", "content": f"Please summarize the following paper within 30 words in English. Explain in clear, easy-to-understand, and fun language:\n{text}"}
        ]
    )
    return response.choices[0].message.content.strip()
