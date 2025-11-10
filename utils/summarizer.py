import openai
import os

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

def summarize_for_matching(text: str) -> str:
    """
    Member tagging용 요약.
    - 연구 분야, 도메인, 주요 task, 방법, 핵심 키워드를 최대한 보존해서 적게.
    """
    response = client.chat.completions.create(
        model="gpt-4o-mini",
        messages=[
            {
                "role": "system",
                "content": (
                    "You are an assistant that writes concise but information-dense summaries "
                    "for research paper matching in an HCI research lab."
                ),
            },
            {
                "role": "user",
                "content": (
                    "Summarize the following paper in 3–4 sentences in English.\n"
                    "- Keep important technical keywords and research areas as they are.\n"
                    "- Explicitly mention research field, target domain, main task, methods, "
                    "and key concepts if possible.\n"
                    "- e clear and precise.\n"
                    "- Only output the summary text.\n\n"
                    f"{text}"
                ),
            },
        ],
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
