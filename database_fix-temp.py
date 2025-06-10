import sqlite3
import shutil

# Start from a clean copy of new.db (so you keep comments)
shutil.copyfile("reddit_data_comments.db", "merged.db")

# Connect to both
merged_conn = sqlite3.connect("merged.db")
old_conn = sqlite3.connect("reddit_data_posts.db")

merged_cur = merged_conn.cursor()
old_cur = old_conn.cursor()

# Drop current posts table in merged.db
merged_cur.execute("DROP TABLE IF EXISTS posts")

old_cur.execute("SELECT sql FROM sqlite_master WHERE type='table' AND name='posts'")
row = old_cur.fetchone()

if row is not None:
    create_stmt = row[0]
    merged_cur.execute(create_stmt)
else:
    # Fall back to manually defining the schema
    print("⚠️ No CREATE TABLE statement found in sqlite_master for 'posts'. Using manual schema.")
    merged_cur.execute('''
    CREATE TABLE posts (
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

# Copy over post content
old_cur.execute("SELECT * FROM posts")
rows = old_cur.fetchall()
placeholders = ",".join(["?"] * len(rows[0]))
merged_cur.executemany(f"INSERT INTO posts VALUES ({placeholders})", rows)

merged_conn.commit()
merged_conn.close()
old_conn.close()

print("✅ Merged database created as merged.db")
