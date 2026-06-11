"""
Utility functions for loading the mock listings dataset and wardrobe schema.
Use these in your tool implementations to access the data without re-reading
the files each time.
"""

import json
import os
import sqlite3
from typing import Optional

# Resolve the path to the data directory relative to this file
_DATA_DIR = os.path.join(os.path.dirname(__file__), "..", "data")
DB_PATH = "fitfindr.db"

def init_db():
    """Initialize the SQLite database if it doesn't exist."""
    conn = sqlite3.connect(DB_PATH)
    cursor = conn.cursor()

    # Table for wardrobes
    cursor.execute('''
    CREATE TABLE IF NOT EXISTS wardrobes (
        user_id TEXT PRIMARY KEY,
        wardrobe_json TEXT
    )
    ''')

    # Table for trends
    cursor.execute('''
    CREATE TABLE IF NOT EXISTS trends (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        fetch_date TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
        trends_json TEXT
    )
    ''')

    conn.commit()
    conn.close()

# Initialize DB on module load
init_db()


def load_listings() -> list[dict]:
    """
    Load all mock listings from the dataset.

    Returns:
        A list of listing dictionaries. Each listing has the following fields:
        - id (str)
        - title (str)
        - description (str)
        - category (str): one of tops, bottoms, outerwear, shoes, accessories
        - style_tags (list[str])
        - size (str)
        - condition (str): excellent, good, or fair
        - price (float)
        - colors (list[str])
        - brand (str or None)
        - platform (str): depop, thredUp, or poshmark
    """
    path = os.path.join(_DATA_DIR, "listings.json")
    with open(path, "r", encoding="utf-8") as f:
        return json.load(f)


def load_wardrobe_schema() -> dict:
    """
    Load the wardrobe schema, including the example wardrobe and empty template.

    Returns:
        A dictionary containing:
        - schema: the field definitions for a wardrobe item
        - example_wardrobe: a sample wardrobe with 10 items
        - empty_wardrobe: a starting template for a new user
    """
    path = os.path.join(_DATA_DIR, "wardrobe_schema.json")
    with open(path, "r", encoding="utf-8") as f:
        return json.load(f)


def get_example_wardrobe() -> dict:
    """
    Convenience function — returns just the example wardrobe items list.

    Returns:
        A wardrobe dict with an 'items' key containing a list of wardrobe items.
    """
    schema = load_wardrobe_schema()
    return schema["example_wardrobe"]


def get_empty_wardrobe() -> dict:
    """
    Convenience function — returns an empty wardrobe template.

    Returns:
        A wardrobe dict with an empty 'items' list.
    """
    schema = load_wardrobe_schema()
    return schema["empty_wardrobe"]


def save_wardrobe(user_id: str, wardrobe: dict):
    """Save wardrobe to SQLite database."""
    conn = sqlite3.connect(DB_PATH)
    cursor = conn.cursor()
    cursor.execute(
        "INSERT OR REPLACE INTO wardrobes (user_id, wardrobe_json) VALUES (?, ?)",
        (user_id, json.dumps(wardrobe))
    )
    conn.commit()
    conn.close()


def load_wardrobe(user_id: str) -> Optional[dict]:
    """Load wardrobe from SQLite database."""
    conn = sqlite3.connect(DB_PATH)
    cursor = conn.cursor()
    cursor.execute("SELECT wardrobe_json FROM wardrobes WHERE user_id = ?", (user_id,))
    row = cursor.fetchone()
    conn.close()
    if row:
        return json.loads(row[0])
    return None


def save_trends(trends: list[str]):
    """Save trends to SQLite database."""
    conn = sqlite3.connect(DB_PATH)
    cursor = conn.cursor()
    cursor.execute(
        "INSERT INTO trends (trends_json) VALUES (?)",
        (json.dumps(trends),)
    )
    conn.commit()
    conn.close()


def load_latest_trends() -> Optional[tuple[str, list[str]]]:
    """Load latest trends and their fetch date."""
    conn = sqlite3.connect(DB_PATH)
    cursor = conn.cursor()
    cursor.execute("SELECT fetch_date, trends_json FROM trends ORDER BY fetch_date DESC LIMIT 1")
    row = cursor.fetchone()
    conn.close()
    if row:
        return row[0], json.loads(row[1])
    return None


# --- Quick sanity check ---
if __name__ == "__main__":
    listings = load_listings()
    print(f"Loaded {len(listings)} listings.")
    print(f"First listing: {listings[0]['title']} — ${listings[0]['price']}")

    wardrobe = get_example_wardrobe()
    print(f"\nExample wardrobe has {len(wardrobe['items'])} items.")
    print(f"First item: {wardrobe['items'][0]['name']}")
