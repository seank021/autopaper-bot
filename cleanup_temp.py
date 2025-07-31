import os
import time

def cleanup_temp(path="temp", max_age_sec=86400): # 1 day
    now = time.time()
    deleted = []
    for fname in os.listdir(path):
        fpath = os.path.join(path, fname)
        if os.path.isfile(fpath) and now - os.path.getmtime(fpath) > max_age_sec:
            os.remove(fpath)
            deleted.append(fname)
    print(f"[cleanup] Removed {len(deleted)} old files: {deleted}")

if __name__ == "__main__":
    cleanup_temp()
