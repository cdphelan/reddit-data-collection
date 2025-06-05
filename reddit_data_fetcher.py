import praw
import sqlite3
import time
import random
import os
from datetime import datetime
from praw.models import MoreComments

# === CONFIGURATION ===
from reddit_keys import REDDIT_CLIENT_ID, REDDIT_CLIENT_SECRET, REDDIT_USER_AGENT

SUBREDDITS = ["sleep","ChronicPain","depression","Anxiety","insomnia",
                "Fibromyalgia", "Endo", "endometriosis", "ehlersdanlos", "POTS",
                "Anxietyhelp","HealthAnxiety","dpdr","AnxietyDepression","socialanxiety","OCD",
                "Health","mentalhealth","AskDocs","ChronicIllness" 
                ]

# SUBREDDITS = ["trees","weed","Petioles","cannabis","Marijuana",
# "eldertrees","entwives","leaves","saplings","delta8","treedibles","vaporents",
# "420","cannabiscultivation","microgrowery",
# "CBD","CBDflower","CBDhempBuds","cbdinfo","CBDoil","CBDOilReviews","cbg","CultoftheFranklin","Dabs","hempflowers",
# "MMJ","noids","rosin","Waxpen"]

SORTS = ["new", "top", "controversial"]
TIME_FILTERS = ["day", "week", "month", "year", "all"]
MAX_POSTS_PER_COMBO = 1000 #change to 1000 when done debugging
# DB_PATH = "reddit_data-cann.db" #cannabis db
DB_PATH = "reddit_data.db" #health db


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
    time_filter TEXT,
    fetched_utc INTEGER
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

# === HELPER FUNCTIONS TO FETCH & STORE ===
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
        INSERT OR IGNORE INTO posts (
            id, subreddit, title, selftext, created_utc,
            score, num_comments, sort, time_filter, fetched_utc
        )
        VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
    ''', (
        post.id,
        subreddit,
        post.title,
        post.selftext,
        int(post.created_utc),
        post.score,
        post.num_comments,
        sort,
        time_filter,
        int(time.time())  # Current UTC timestamp
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

# === COLLECT ALL DATA (INITIAL SCRAPE) ===
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
                    time.sleep(random.uniform(0.4, 0.8))  # Sleep between posts, randomized to avoid detection

                    # Fetch and store comments - removing this bc it took way too long, moved to backfill_missing_comments()
                    # try:
                    #     post.comments.replace_more(limit=0)
                    #     for comment in post.comments.list():
                    #         if isinstance(comment, MoreComments):
                    #             continue
                    #         store_comment(comment, post.id)
                    #         time.sleep(random.uniform(0.01, 0.1))  # Sleep between comments
                    # except Exception as e:
                    #     print(f"Failed to fetch comments for post {post.id}: {e}")

    print("Data collection complete.")

# === UPDATE DATA ===
# Scrape all new posts that have posted since last collection
# and check for new comments in posts that were less than 72 hours old when they were collected
def refresh_recent_and_new_posts():
    now = int(time.time())
    cutoff = now - 72 * 3600  # 72 hours ago

    for subreddit in SUBREDDITS:
        print(f"\nChecking new posts in r/{subreddit}")
        pcount = 0
        sub = reddit.subreddit(subreddit)
        
        # Fetch up to 1000 newest posts
        try:
            new_posts = fetch_with_backoff(sub.new(limit=MAX_POSTS_PER_COMBO))
        except Exception as e:
            print(f"Failed to fetch new posts from r/{subreddit}: {e}")
            continue

        for post in new_posts:
            print(f"Processing post {post.id}...")
            if already_fetched(post.id):
                print(f"\tPost {post.id} already processed.")
                continue
            store_post(post, subreddit, sort="new", time_filter=None)
            pcount += 1
            time.sleep(random.uniform(1, 2))

            try:
                post.comments.replace_more(limit=0)
                for comment in post.comments.list():
                    if isinstance(comment, MoreComments):
                        continue
                    store_comment(comment, post.id)
                    time.sleep(random.uniform(0.1, 0.5))
            except Exception as e:
                print(f"Error fetching comments for post {post.id}: {e}")
            print(f"Stored {pcount} new posts from r/{subreddit}")
        
        # Now check previously collected posts that were young at fetch time
        print(f"[🔄] Refreshing comment threads for recent posts in r/{subreddit}")
        cur.execute('''
            SELECT id, created_utc, fetched_utc FROM posts
            WHERE subreddit = ? AND fetched_utc - created_utc < ?
        ''', (subreddit, 72 * 3600))

        rows = cur.fetchall()
        for post_id, created, fetched in rows:
            print(f"Refreshing comments for {post_id}")
            try:
                post = reddit.submission(id=post_id)
                post.comments.replace_more(limit=0)
                for comment in post.comments.list():
                    if isinstance(comment, MoreComments):
                        continue
                    if already_fetched_comment(comment.id):
                        continue
                    store_comment(comment, post.id)
                    time.sleep(random.uniform(0.1, 0.5))
            except Exception as e:
                print(f"Error refreshing comments for {post_id}: {e}")

def backfill_missing_comments():
    #Get all post IDs
    cur.execute("SELECT id FROM posts")
    all_post_ids = [row[0] for row in cur.fetchall()]

    #Get all post_ids that already have comments
    cur.execute("SELECT DISTINCT post_id FROM comments")
    posts_with_comments = set(row[0] for row in cur.fetchall())

    #Identify posts that are missing comments
    posts_missing_comments = list(set(all_post_ids) - posts_with_comments)  # Convert back to list if needed

    print(f"Found {len(posts_missing_comments)} posts missing comments.")

    #Iterate through and collect comments
    for i, post_id in enumerate(posts_missing_comments, 1):
        print(f"\n[{i}/{len(posts_missing_comments)}] Backfilling comments for post {post_id}...")
        try:
            post = reddit.submission(id=post_id)
            post.comments.replace_more(limit=0)
            for comment in post.comments.list():
                if isinstance(comment, MoreComments):
                    continue
                store_comment(comment, post_id)
                time.sleep(random.uniform(0.01, 0.1))  # Sleep between comments
        except Exception as e:
            print(f"Failed to fetch comments for post {post_id}: {e}")


#select one of these two functions depending on whether doing a first collection or an update
# collect_reddit_data() #initial data collection
refresh_recent_and_new_posts() #daily check-in after
# backfill_missing_comments()
conn.close()
