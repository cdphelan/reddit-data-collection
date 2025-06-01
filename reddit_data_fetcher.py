import praw
import sqlite3
import time
import random
import os
from datetime import datetime
from praw.models import MoreComments

# === CONFIGURATION ===
REDDIT_CLIENT_ID = "kcHXc5QNzUSnBDPh2HrOtw"
REDDIT_CLIENT_SECRET = "KQhUO_jeYEIGEnD-2Z2bxtoiQ8vmuw"
REDDIT_USER_AGENT = "CannTalk research scraper (by u/dreamfall17)"

SUBREDDITS = ["sleep", "insomnia",
                "ChronicPain", "Fibromyalgia", "Endo", "endometriosis", "ehlersdanlos", "POTS",
                "depression","Anxiety","socialanxiety","OCD","Anxietyhelp","HealthAnxiety",
                "dpdr","AnxietyDepression",
                "Health","mentalhealth","AskDocs","ChronicIllness"]

SORTS = ["new", "top", "controversial"]
TIME_FILTERS = ["day", "week", "month", "year", "all"]
MAX_POSTS_PER_COMBO = 1000 #change to 1000 when done debugging
DB_PATH = "reddit_data.db"

# === INITIALIZE DB ===
conn = sqlite3.connect(DB_PATH)
cur = conn.cursor()

cur.execute('''
CREATE TABLE IF NOT EXISTS posts (
    id TEXT PRIMARY KEY,
    subreddit TEXT,
    title TEXT,
    selftext TEXT,
    created_utc INTEGER,
    score INTEGER,
    num_comments INTEGER,
    sort TEXT,
    time_filter TEXT
)
''')

cur.execute('''
CREATE TABLE IF NOT EXISTS comments (
    id TEXT PRIMARY KEY,
    post_id TEXT,
    body TEXT,
    created_utc INTEGER,
    score INTEGER,
    parent_id TEXT,
    FOREIGN KEY(post_id) REFERENCES posts(id)
)
''')

conn.commit()

# === INITIALIZE PRAW ===
reddit = praw.Reddit(
    client_id=REDDIT_CLIENT_ID,
    client_secret=REDDIT_CLIENT_SECRET,
    user_agent=REDDIT_USER_AGENT
)

# manual testing for debugging
# sub = reddit.subreddit("depression")
# posts = list(sub.new(limit=1000))
# print(f"Length of new posts fetched: {len(posts)}")

def fetch_with_backoff(generator):
    results = []
    attempts = 0
    while attempts < 5:
        try:
            for item in generator:
                results.append(item)
            print(f"Successfully fetched {len(results)} items")
            return results
        except Exception as e:
            wait_time = 2 ** attempts
            print(f"Error: {e}. Retrying in {wait_time} seconds...")
            time.sleep(wait_time)
            attempts += 1
    return results

def already_fetched(post_id):
    cur.execute("SELECT 1 FROM posts WHERE id = ?", (post_id,))
    return cur.fetchone() is not None

def store_post(post, subreddit, sort, time_filter):
    cur.execute('''
        INSERT OR IGNORE INTO posts (id, subreddit, title, selftext, created_utc, score, num_comments, sort, time_filter)
        VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
    ''', (
        post.id, subreddit, post.title, post.selftext, int(post.created_utc),
        post.score, post.num_comments, sort, time_filter
    ))
    conn.commit()

def store_comment(comment, post_id):
    cur.execute('''
        INSERT OR IGNORE INTO comments (id, post_id, parent_id, body, created_utc, score)
        VALUES (?, ?, ?, ?, ?, ?)
    ''', (
        comment.id, post_id, comment.parent_id, comment.body, int(comment.created_utc), comment.score
    ))
    conn.commit()

def collect_reddit_data():
    for subreddit in SUBREDDITS:
        for sort in SORTS:
            filters = TIME_FILTERS if sort in ["top", "controversial"] else [None]

            for time_filter in filters:
                print(f"\nCollecting: r/{subreddit} | sort={sort} | time={time_filter}")
                sub = reddit.subreddit(subreddit)
                fetch_args = {"limit": MAX_POSTS_PER_COMBO}

                # Get the listing method (e.g., sub.top, sub.new)
                get_posts = getattr(sub, sort)

                try:
                    if sort in ["top", "controversial"] and time_filter:
                        posts = fetch_with_backoff(get_posts(time_filter=time_filter, limit=MAX_POSTS_PER_COMBO))
                    else:
                        posts = fetch_with_backoff(get_posts(limit=MAX_POSTS_PER_COMBO))
                    print(f"Fetched {len(posts)} posts from r/{subreddit} sorted by {sort}, time={time_filter}")
                except Exception as e:
                    print(f"Error fetching posts for r/{subreddit} sorted by {sort}: {e}")
                    continue

                for post in posts:
                    print(f"Processing post {post.id}...")

                    if already_fetched(post.id):
                        print(f"\tPost {post.id} already processed.")
                        continue

                    store_post(post, subreddit, sort, time_filter)
                    time.sleep(random.uniform(1, 3))  # Sleep between posts

                    # Fetch and store comments
                    try:
                        post.comments.replace_more(limit=0)
                        for comment in post.comments.list():
                            if isinstance(comment, MoreComments):
                                continue
                            store_comment(comment, post.id)
                            time.sleep(random.uniform(0.01, 0.1))  # Sleep between comments
                    except Exception as e:
                        print(f"Failed to fetch comments for post {post.id}: {e}")

    print("Data collection complete.")

collect_reddit_data()
conn.close()
