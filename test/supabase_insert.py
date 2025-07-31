import os
import sys
sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))

from utils.supabase_db import insert_metadata
from utils.path_utils import get_thread_hash

thread_ts = "1753967488.826379"  # 테스트용
thread_hash = get_thread_hash(thread_ts)

insert_metadata(thread_hash, {
    "user_id": "U123TEST",
    "channel_id": "C456TEST",
    "timestamp": thread_ts,
    "filename": "test-paper.pdf",
    "source": "https://arxiv.org/abs/2307.00001"
})

print(f"[OK] Inserted metadata for {thread_hash}")
