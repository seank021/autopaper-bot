import openai
import os
from dotenv import load_dotenv

load_dotenv()
client = openai.OpenAI(api_key=os.getenv("OPENAI_API_KEY"))

# Summarize text (paper) using OpenAI's GPT model
def summarize_text(text):
    text = text
    response = client.chat.completions.create(
        model="gpt-4o-mini",
        messages=[
            {"role": "system", "content": "You are a helpful assistant that summarizes academic papers."},
            {"role": "user", "content": f"Please summarize the following paper within 30 words in English. Explain in clear, easy-to-understand, and fun language. Only provide the summary without any additional commentary:\n{text}"}
        ]
    )
    return response.choices[0].message.content.strip()

# Extract keywords from text (paper) using OpenAI's GPT model
def extract_keywords(text):
    response = client.chat.completions.create(
        model="gpt-4o-mini",
        messages=[
            {"role": "system", "content": "You are a helpful assistant that extracts keywords from academic papers."},
            {"role": "user", "content": f"Please extract 5 keywords from the following paper. Return them as a comma-separated list:\n{text}"}
        ]
    )
    return response.choices[0].message.content.strip().split(', ')
