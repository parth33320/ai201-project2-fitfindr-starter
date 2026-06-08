"""
tools.py

The three required FitFindr tools. Each tool is a standalone function that
can be called and tested independently before being wired into the agent loop.

Complete and test each tool before moving to agent.py.

Tools:
    search_listings(description, size, max_price)  → list[dict]
    suggest_outfit(new_item, wardrobe)              → str
    create_fit_card(outfit, new_item)               → str
"""

import os

from dotenv import load_dotenv
from groq import Groq

from utils.data_loader import load_listings

load_dotenv()


# ── Groq client ───────────────────────────────────────────────────────────────

def _get_groq_client():
    """Initialize and return a Groq client using GROQ_API_KEY from .env."""
    api_key = os.environ.get("GROQ_API_KEY")
    if not api_key:
        raise ValueError(
            "GROQ_API_KEY not set. Add it to a .env file in the project root."
        )
    return Groq(api_key=api_key)


# ── Tool 1: search_listings ───────────────────────────────────────────────────

def search_listings(
    description: str,
    size: str | None = None,
    max_price: float | None = None,
) -> list[dict]:
    """
    Search the mock listings dataset for items matching the description,
    optional size, and optional price ceiling.

    Args:
        description: Keywords describing what the user is looking for
                     (e.g., "vintage graphic tee").
        size:        Size string to filter by, or None to skip size filtering.
                     Matching is case-insensitive (e.g., "M" matches "S/M").
        max_price:   Maximum price (inclusive), or None to skip price filtering.

    Returns:
        A list of matching listing dicts, sorted by relevance (best match first).
        Returns an empty list if nothing matches — does NOT raise an exception.
    """
    all_listings = load_listings()
    filtered_listings = []

    # 1. Filter by max_price and size
    for item in all_listings:
        if max_price is not None and item["price"] > max_price:
            continue

        if size is not None:
            if size.lower() not in item["size"].lower():
                continue

        filtered_listings.append(item)

    # 2. Score by keyword overlap
    scored_listings = []
    query_keywords = description.lower().split()

    for item in filtered_listings:
        score = 0
        # Searchable text: title, description, and style_tags
        searchable_text = (
            item["title"] + " " +
            item["description"] + " " +
            " ".join(item["style_tags"])
        ).lower()

        for kw in query_keywords:
            if kw in searchable_text:
                score += 1

        if score > 0:
            scored_listings.append((score, item))

    # 3. Sort by score, highest first
    scored_listings.sort(key=lambda x: x[0], reverse=True)

    return [item for score, item in scored_listings]


# ── Tool 2: suggest_outfit ────────────────────────────────────────────────────

def suggest_outfit(new_item: dict, wardrobe: dict) -> str:
    """
    Given a thrifted item and the user's wardrobe, suggest 1–2 complete outfits.

    Args:
        new_item: A listing dict (the item the user is considering buying).
        wardrobe: A wardrobe dict with an 'items' key containing a list of
                  wardrobe item dicts. May be empty — handle this gracefully.

    Returns:
        A non-empty string with outfit suggestions.
        If the wardrobe is empty, offer general styling advice for the item
        rather than raising an exception or returning an empty string.
    """
    client = _get_groq_client()

    item_info = (
        f"Item: {new_item['title']}\n"
        f"Description: {new_item['description']}\n"
        f"Category: {new_item['category']}\n"
        f"Style Tags: {', '.join(new_item['style_tags'])}\n"
        f"Colors: {', '.join(new_item['colors'])}"
    )

    items = wardrobe.get("items", [])

    if not items:
        prompt = (
            f"I just found this item secondhand:\n\n{item_info}\n\n"
            "My wardrobe is currently empty. Can you give me some general styling "
            "advice for this piece? What types of items would it pair well with, "
            "and what kind of vibe does it have?"
        )
    else:
        wardrobe_info = "\n".join([
            f"- {item['name']} ({item['category']}): {', '.join(item['style_tags'])}"
            for item in items
        ])
        prompt = (
            f"I just found this item secondhand:\n\n{item_info}\n\n"
            "And here is my current wardrobe:\n"
            f"{wardrobe_info}\n\n"
            "Please suggest 1-2 complete outfits using the new item and specific "
            "pieces from my wardrobe. Be creative but keep the style cohesive!"
        )

    chat_completion = client.chat.completions.create(
        messages=[
            {
                "role": "system",
                "content": "You are a helpful and stylish personal fashion assistant called FitFindr.",
            },
            {
                "role": "user",
                "content": prompt,
            }
        ],
        model="llama-3.3-70b-versatile",
    )

    return chat_completion.choices[0].message.content


# ── Tool 3: create_fit_card ───────────────────────────────────────────────────

def create_fit_card(outfit: str, new_item: dict) -> str:
    """
    Generate a short, shareable outfit caption for the thrifted find.

    Args:
        outfit:   The outfit suggestion string from suggest_outfit().
        new_item: The listing dict for the thrifted item.

    Returns:
        A 2–4 sentence string usable as an Instagram/TikTok caption.
        If outfit is empty or missing, return a descriptive error message
        string — do NOT raise an exception.
    """
    if not outfit or not outfit.strip():
        return "Could not generate fit card due to missing outfit details."

    client = _get_groq_client()

    prompt = (
        f"I'm styling this new thrifted find: {new_item['title']} (${new_item['price']}) "
        f"from {new_item['platform']}.\n\n"
        f"Here's the outfit idea: {outfit}\n\n"
        "Write a short, shareable caption for an Instagram or TikTok OOTD post. "
        "The caption should:\n"
        "- Be 2-4 sentences long.\n"
        "- Feel casual and authentic (not a product description).\n"
        f"- Naturally mention the item name ({new_item['title']}), "
        f"the price (${new_item['price']}), and the platform ({new_item['platform']}) once each.\n"
        "- Capture the outfit vibe.\n"
        "Do not use hashtags unless they feel very natural."
    )

    chat_completion = client.chat.completions.create(
        messages=[
            {
                "role": "system",
                "content": "You are a trendy fashion influencer who loves thrifting.",
            },
            {
                "role": "user",
                "content": prompt,
            }
        ],
        model="llama-3.3-70b-versatile",
        temperature=0.9,
    )

    return chat_completion.choices[0].message.content.strip().replace('"', '')
