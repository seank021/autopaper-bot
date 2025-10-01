import re
import requests
import os

SUPPORTED_SOURCES = {
    "arxiv": {
        "pattern": r"(https?://(?:www\.)?(?:arxiv\.org|ar5iv\.org)/(?:abs|pdf|html)/(\d+\.\d+(?:v\d+)?))",
        "pdf_url": lambda arxiv_id: f"https://arxiv.org/pdf/{arxiv_id}.pdf"
    },
    # TODO: Add more sources
}

def process_link_download(message_text, save_path):
    os.makedirs(os.path.dirname(save_path), exist_ok=True)

    for source, config in SUPPORTED_SOURCES.items():
        match = re.search(config["pattern"], message_text)
        if match:
            source_link = match.group(1)
            paper_id = match.group(2)
            pdf_url = config["pdf_url"](paper_id)
            try:
                response = requests.get(pdf_url)
                if response.status_code == 200:
                    with open(save_path, "wb") as f:
                        f.write(response.content)
                    filename = os.path.basename(pdf_url)
                    return True, source_link, filename
                else:
                    print(f"PDF 요청 실패: {response.status_code}")
            except Exception as e:
                print(f"다운로드 예외 발생: {e}")
    return False, None, None
