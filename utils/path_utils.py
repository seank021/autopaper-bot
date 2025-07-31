import os
import hashlib

def get_thread_hash(thread_ts):
    return hashlib.sha256(thread_ts.encode()).hexdigest()[:8]

def get_pdf_path_from_thread(thread_ts, base_dir="temp"):
    thread_hash = get_thread_hash(thread_ts)
    os.makedirs(base_dir, exist_ok=True)
    return os.path.join(base_dir, f"{thread_hash}.pdf")

