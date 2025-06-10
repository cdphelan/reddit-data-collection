#get the posts for the orphaned comments in healthdb.comments bc i accidentally dropped healthdb.posts
#shouldn't need to be run repeatedly

import sqlite3
import praw
import time
from datetime import datetime
import random

from reddit_keys import REDDIT_CLIENT_ID, REDDIT_CLIENT_SECRET, REDDIT_USER_AGENT

# === INITIALIZE PRAW ===
reddit = praw.Reddit(
    client_id=REDDIT_CLIENT_ID,
    client_secret=REDDIT_CLIENT_SECRET,
    user_agent=REDDIT_USER_AGENT
)

# --- Connect to DB ---
conn = sqlite3.connect("reddit_data-health.db")
cur = conn.cursor()

# --- Step 1: Get orphan post_ids ---
cur.execute("""
    SELECT DISTINCT c.post_id
    FROM comments c
    LEFT JOIN posts p ON c.post_id = p.id
    WHERE p.id IS NULL
""")
orphan_ids = [row[0] for row in cur.fetchall()]
print(f"Found {len(orphan_ids)} orphan post_ids.")

# --- Step 2: Fetch missing posts ---
now_ts = int(time.time())
fetched = []
for post_id in orphan_ids:
    try:
        clean_id = post_id.split('_')[-1]  # remove 't3_' if present
        submission = reddit.submission(id=clean_id)
        fetched.append((
            submission.id,
            submission.subreddit.display_name,
            submission.title,
            submission.selftext,
            int(submission.created_utc),
            submission.score,
            submission.num_comments,
            'orphan',       # sort
            None,           # time_filter
            now_ts          # fetched_utc
        ))
        time.sleep(random.uniform(0.1, 0.5))
    except Exception as e:
        print(f"Error fetching {post_id}: {e}")
        time.sleep(5)  # cool down on error

# --- Step 3: Insert into posts table ---
cur.executemany("""
    INSERT OR IGNORE INTO posts 
    (id, subreddit, title, selftext, created_utc, score, num_comments, sort, time_filter, fetched_utc)
    VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
""", fetched)

conn.commit()
conn.close()
print(f"✅ Inserted {len(fetched)} recovered posts with sort='orphan'.")
