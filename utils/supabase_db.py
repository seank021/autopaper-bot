from supabase import create_client
import os
from dotenv import load_dotenv

load_dotenv()

SUPABASE_URL = os.getenv("SUPABASE_URL")
SUPABASE_KEY = os.getenv("SUPABASE_KEY")
supabase = create_client(SUPABASE_URL, SUPABASE_KEY)

def insert_metadata(thread_hash, metadata: dict):
    data = {**metadata, "thread_hash": thread_hash}
    supabase.table("metadata").insert(data).execute()

def get_metadata(thread_hash):
    res = supabase.table("metadata").select("*").eq("thread_hash", thread_hash).execute()
    return res.data[0] if res.data else None
