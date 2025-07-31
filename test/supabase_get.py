import os
import sys
sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))

from utils.supabase_db import get_metadata
from utils.path_utils import get_thread_hash

thread_ts = "1753967488.826379"
thread_hash = get_thread_hash(thread_ts)

meta = get_metadata(thread_hash)
print("[RESULT]", meta)
