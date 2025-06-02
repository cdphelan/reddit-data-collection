
# Reddit Data Fetcher

This script fetches posts and comments from a list of specified subreddits using the Reddit API via the PRAW library. The collected data is stored in a local SQLite database for further analysis.

---

## 📌 Features

- Supports multiple subreddits, sorting methods, and time filters.
- Stores posts and comments in a SQLite database.
- Tracks and skips already fetched posts.
- Fetches comment threads and captures parent-child relationships.
- Includes exponential backoff and random sleep delays to avoid rate-limiting.

---

## ⚙️ Configuration

Environment variables required:
- `REDDIT_CLIENT_ID`
- `REDDIT_CLIENT_SECRET`
- `REDDIT_USER_AGENT`

These are used to authenticate with the Reddit API via PRAW.

```python
SUBREDDITS = ["AskDocs", "MMJ", "eldertrees", "CBD", "medicalmarijuana", "marijuana", "PetCBD"]
SORTS = ["new", "top", "controversial"]
TIME_FILTERS = ["day", "week", "month", "year", "all"]
MAX_POSTS_PER_COMBO = 1000
DB_PATH = "reddit_health_data.db"
```

---

## 🗃️ Database Schema

### posts
| Column        | Type    | Description                        |
|---------------|---------|------------------------------------|
| id            | TEXT    | Reddit post ID (primary key)       |
| subreddit     | TEXT    | Subreddit name                     |
| title         | TEXT    | Post title                         |
| selftext      | TEXT    | Post body                          |
| created_utc   | INTEGER | Timestamp                          |
| score         | INTEGER | Reddit score                       |
| num_comments  | INTEGER | Number of comments                 |
| sort          | TEXT    | Sorting method (top/new/controversial) |
| time_filter   | TEXT    | Time period for top/controversial  |

### comments
| Column        | Type    | Description                         |
|---------------|---------|-------------------------------------|
| id            | TEXT    | Reddit comment ID (primary key)     |
| post_id       | TEXT    | Associated post ID                  |
| body          | TEXT    | Comment text                        |
| created_utc   | INTEGER | Timestamp                           |
| score         | INTEGER | Reddit score                        |
| parent_id     | TEXT    | Parent comment or post ID           |

---

## 🔁 Main Functionality

### `collect_reddit_data()`
Iterates over all combinations of subreddits, sort types, and time filters. For each post:
- Skips if already processed.
- Stores post and its metadata.
- Retrieves comments and stores them with a sleep delay between each.

### `store_post(post, subreddit, sort, time_filter)`
Inserts post metadata into the `posts` table using `INSERT OR IGNORE`.

### `store_comment(comment, post_id)`
Inserts comment metadata into the `comments` table, including `parent_id`.

### `already_fetched(post_id)`
Checks whether the post ID exists in the database before processing.

---

## ⏱️ Rate Limiting

To avoid triggering Reddit's rate limits:
- Random sleep between 1–3 seconds between posts.
- Random sleep between 0.01–0.1 seconds between comments.
- Exponential backoff retry logic for failed API calls.

---

## ▶️ Running the Script

```bash
streamlit run reddit_data_fetcher.py
```

Ensure your environment variables for Reddit API access are configured beforehand.

---

## 📂 Output

- SQLite database at the specified `DB_PATH`.
- `posts` and `comments` tables populated with fresh data.
- Safe to re-run daily—script skips posts it already collected.

---

## 🧠 Notes

- Maximum Reddit API access per listing (e.g. `new`, `top`) is 1000 posts.
- `replace_more(limit=0)` ensures all comments are flattened for scraping.

---
