import re
import requests
import os

SUPPORTED_SOURCES = {
    "arxiv": {
        "pattern": r"(https?://(?:arxiv\.org/abs/|ar5iv\.org/html/)(\d+\.\d+))",
        "pdf_url": lambda arxiv_id: f"https://arxiv.org/pdf/{arxiv_id}.pdf"
    },
    # TODO: Add more sources here (e.g., ACL Anthology, OpenReview)
}

def download_pdf_from_link(message_text, save_path="temp/temp.pdf"):
    os.makedirs(os.path.dirname(save_path), exist_ok=True)

    for source, config in SUPPORTED_SOURCES.items():
        match = re.search(config["pattern"], message_text)
        if match:
            paper_id = match.group(2)
            pdf_url = config["pdf_url"](paper_id)
            print(f"[{source}] PDF URL: {pdf_url}")
            return _download_pdf(pdf_url, save_path)
    return False

def _download_pdf(pdf_url, save_path):
    try:
        response = requests.get(pdf_url)
        if response.status_code == 200:
            with open(save_path, "wb") as f:
                f.write(response.content)
            return True
        else:
            print(f"PDF 요청 실패: status {response.status_code}")
    except Exception as e:
        print(f"다운로드 예외 발생: {e}")
    return False
