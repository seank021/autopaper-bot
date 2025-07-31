import openai
import os
from dotenv import load_dotenv

load_dotenv()
client = openai.OpenAI(api_key=os.getenv("OPENAI_API_KEY"))

def summarize_text(text):
    text = text[:3000] # OpenAI API has a token limit, so we truncate the text
    response = client.chat.completions.create(
        model="gpt-4o",
        messages=[
            {"role": "system", "content": "You are a helpful assistant that summarizes academic papers."},
            {"role": "user", "content": f"Please summarize the following paper within one sentence in English:\n{text}"}
        ]
    )
    return response.choices[0].message.content.strip()
