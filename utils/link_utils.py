import re
import requests
import os

def download_pdf_from_link(message_text, save_path="temp/temp.pdf"):
    """
    Detects supported paper links (arXiv/ar5iv) and downloads the PDF to save_path.
    Returns True if successful, False otherwise.
    """
    os.makedirs(os.path.dirname(save_path), exist_ok=True)

    # Match arXiv or ar5iv
    match = re.search(r"(https?://(?:arxiv\.org/abs/|ar5iv\.org/html/)(\d+\.\d+))", message_text)
    if match:
        arxiv_id = match.group(2)
        pdf_url = f"https://arxiv.org/pdf/{arxiv_id}.pdf"
        print(f"arXiv 링크: {pdf_url}")

        try:
            response = requests.get(pdf_url)
            if response.status_code == 200:
                with open(save_path, "wb") as f:
                    f.write(response.content)
                print("PDF 다운로드 완료")
                return True
            else:
                print(f"PDF 요청 실패: status {response.status_code}")
        except Exception as e:
            print(f"Exception: {e}")

    # TODO: Add support for ACL Anthology, OpenReview, etc.
    
    return False
