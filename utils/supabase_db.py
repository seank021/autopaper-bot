from supabase import create_client
import os
from dotenv import load_dotenv

load_dotenv()

SUPABASE_URL = os.getenv("SUPABASE_URL")
SUPABASE_KEY = os.getenv("SUPABASE_KEY")
supabase = create_client(SUPABASE_URL, SUPABASE_KEY)

# Paper metadata
def insert_metadata(thread_hash, metadata: dict):
    data = {**metadata, "thread_hash": thread_hash}
    supabase.table("metadata").insert(data).execute()

def get_metadata(thread_hash):
    res = supabase.table("metadata").select("*").eq("thread_hash", thread_hash).execute()
    return res.data[0] if res.data else None

# Conversation logs
def insert_log(thread_hash, role, message, user_id=None, timestamp=None):
    data = {
        "thread_hash": thread_hash,
        "role": role,
        "message": message,
        "user_id": user_id,
        "timestamp": timestamp
    }
    return supabase.table("conversation_logs").insert(data).execute()

def get_logs(thread_hash, limit=10):
    result = supabase.table("conversation_logs") \
        .select("role,message") \
        .eq("thread_hash", thread_hash) \
        .order("timestamp", desc=False) \
        .limit(limit) \
        .execute()
    return result.data if result.data else []

# Members
def insert_member(slack_id, name, keywords, interests, current_projects, embedding):
    data = {
        "slack_id": slack_id,
        "name": name,
        "keywords": keywords,
        "interests": interests,
        "current_projects": current_projects,
        "embedding": embedding # dict → jsonb
    }
    return supabase.table("members").insert(data).execute()

def upsert_member(slack_id, name, keywords, interests, current_projects, embedding):
    data = {
        "slack_id": slack_id,
        "name": name,
        "keywords": keywords,
        "interests": interests,
        "current_projects": current_projects,
        "embedding": embedding
    }
    return supabase.table("members").upsert(data).execute()

def remove_member(slack_id):
    return supabase.table("members").delete().eq("slack_id", slack_id).execute()

def get_member(slack_id):
    result = supabase.table("members").select("*").eq("slack_id", slack_id).execute()
    return result.data[0] if result.data else None

def get_all_members():
    result = supabase.table("members").select("*").execute()
    return result.data if result.data else []
