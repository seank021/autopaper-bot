import os
from utils.supabase_db import get_logs
import openai

client = openai.OpenAI(api_key=os.getenv("OPENAI_API_KEY"))

def answer_question(context: str, question: str, thread_hash: str, max_history: int = 10) -> str:
    logs = get_logs(thread_hash, limit=max_history)
    messages = []

    # Previous conversation logs
    for log in logs:
        messages.append({
            "role": log["role"],
            "content": log["message"]
        })

    # Current question
    messages.append({"role": "user", "content": question})

    # Paper context as a system message
    messages.insert(0, {
        "role": "system",
        "content": (
            "You are a helpful academic assistant. Keep your answers concise and to the point, optimized for mobile reading. Answer in maximum 3 sentences. "
            "Only include the essential details unless further explanation is requested. "
            "The following is the content of the research paper you will refer to:\n\n" + context.strip()
        )
    })

    try:
        response = client.chat.completions.create(
            model="gpt-4o-mini",
            messages=messages,
        )
        return response.choices[0].message.content.strip()
    except Exception as e:
        print(f"[OpenAI Error] {e}")
        return "I'm sorry, but I couldn't process your request at this time."
