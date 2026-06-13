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
import re
import statistics

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

    # 2. Score by keyword overlap (STRICT AND matching)
    scored_listings = []
    query_keywords = description.lower().split()

    if not query_keywords:
        return []

    for item in filtered_listings:
        score = 0
        # Searchable text: title, description, and style_tags
        searchable_text = (
            item["title"] + " " +
            item["description"] + " " +
            " ".join(item["style_tags"])
        ).lower()

        all_keywords_match = True
        for kw in query_keywords:
            pattern = rf"\b{re.escape(kw.lower())}\b"
            matches = re.findall(pattern, searchable_text)
            if not matches:
                all_keywords_match = False
                break
            score += len(matches)

        if all_keywords_match:
            scored_listings.append((score, item))

    # 3. Sort by score, highest first
    scored_listings.sort(key=lambda x: x[0], reverse=True)

    return [item for score, item in scored_listings]


# ── Tool 2: suggest_outfit ────────────────────────────────────────────────────

def suggest_outfit(new_item: dict, wardrobe: dict, trends: list[str] | None = None) -> str:
    """
    Given a thrifted item and the user's wardrobe, suggest 1–2 complete outfits.

    Args:
        new_item: A listing dict (the item the user is considering buying).
        wardrobe: A wardrobe dict with an 'items' key containing a list of
                  wardrobe item dicts. May be empty — handle this gracefully.
        trends:   Optional list of current fashion trends to incorporate.

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
    historical_preferences = wardrobe.get("historical_preferences", [])

    trend_context = ""
    if trends:
        trend_context = "Current fashion trends: " + ", ".join(trends) + "\n\n"

    history_context = ""
    if historical_preferences:
        history_context = f"The user has a historical preference for these styles: {', '.join(historical_preferences)}.\n"

    if not items:
        prompt = (
            f"{trend_context}"
            f"{history_context}"
            f"I just found this item secondhand:\n\n{item_info}\n\n"
            "My wardrobe is currently empty. Can you give me some general styling "
            "advice for this piece? What types of items would it pair well with, "
            "and what kind of vibe does it have? "
            "Incorporate relevant current trends if they fit the vibe!\n\n"
            "If historical preferences are provided, use them to provide a specific, "
            "prescriptive style formula tailored to those aesthetics."
        )
    else:
        wardrobe_info = "\n".join([
            f"- {item['name']} ({item['category']}): {', '.join(item['style_tags'])}"
            for item in items
        ])
        prompt = (
            f"{trend_context}"
            f"{history_context}"
            f"I just found this item secondhand:\n\n{item_info}\n\n"
            "And here is my current wardrobe:\n"
            f"{wardrobe_info}\n\n"
            "Please suggest 1-2 complete outfits using the new item and specific "
            "pieces from my wardrobe. Be creative but keep the style cohesive! "
            "Try to lean into current trends if they match the style of the item and wardrobe."
        )

    prompt += (
        "\n\nAt the end of your response, please provide 2-4 core style tags or "
        "descriptive aesthetics that capture the vibe of this suggestion. "
        "Format them exactly like this on a new line: EXTRACTED_TAGS: tag1, tag2"
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


# ── Tool 4: estimate_price_fairness ──────────────────────────────────────────

def estimate_price_fairness(item: dict) -> str:
    """
    Estimate price fairness using fine-grained product detection and a
    two-tier outlier-protected pricing strategy.
    """
    all_listings = load_listings()

    # 1. FINE-GRAINED PRODUCT DETECTION
    keywords = [
        "jean", "hoodie", "sweatshirt", "shorts", "belt", "boot",
        "skirt", "tee", "shirt", "jacket", "coat", "dress", "sneaker"
    ]

    # Mapping for dynamic phrasing
    keyword_phrasing = {
        "jean": ("These jeans", "jeans"),
        "hoodie": ("This hoodie", "hoodies"),
        "sweatshirt": ("This sweatshirt", "sweatshirts"),
        "shorts": ("These shorts", "shorts"),
        "belt": ("This belt", "belts"),
        "boot": ("These boots", "boots"),
        "skirt": ("This skirt", "skirts"),
        "tee": ("This tee", "tees"),
        "shirt": ("This shirt", "shirts"),
        "jacket": ("This jacket", "jackets"),
        "coat": ("This coat", "coats"),
        "dress": ("This dress", "dresses"),
        "sneaker": ("These sneakers", "sneakers")
    }

    category_phrasing = {
        "tops": ("This top", "tops"),
        "bottoms": ("These bottoms", "bottoms"),
        "outerwear": ("This outerwear", "outerwear pieces"),
        "shoes": ("These shoes", "shoes"),
        "accessories": ("This accessory", "accessories")
    }

    def detect_type(listing):
        title = listing.get("title", "").lower()
        description = listing.get("description", "").lower()

        # Check title first
        best_kw = None
        max_pos = -1
        for kw in keywords:
            pos = title.rfind(kw)
            if pos != -1:
                end_pos = pos + len(kw)
                if end_pos > max_pos:
                    max_pos = end_pos
                    best_kw = kw

        if best_kw:
            return best_kw

        # Check description
        for kw in keywords:
            pos = description.rfind(kw)
            if pos != -1:
                end_pos = pos + len(kw)
                if end_pos > max_pos:
                    max_pos = end_pos
                    best_kw = kw

        return best_kw

    detected_type = detect_type(item)

    # Gather items matching the detected type (or fallback to category)
    if detected_type:
        match_items = [l for l in all_listings if detect_type(l) == detected_type and l["id"] != item["id"]]
        display_singular, display_plural = keyword_phrasing[detected_type]
    else:
        match_items = [l for l in all_listings if l["category"] == item["category"] and l["id"] != item["id"]]
        display_singular, display_plural = category_phrasing.get(item["category"], ("This item", "similar items"))

    # 2. FILTER ALL LISTINGS & APPLY OUTLIER PROTECTION
    def get_clean_average(items):
        if not items:
            return None
        prices = sorted([l["price"] for l in items])
        if not prices:
            return None

        med = statistics.median(prices)
        clean_prices = [p for p in prices if (med * 0.2) <= p <= (med * 3.0)]

        if not clean_prices:
            return None
        return sum(clean_prices) / len(clean_prices)

    # 3. TWO-TIER PRICING STRATEGY
    baseline_avg = None
    baseline_msg = ""
    item_brand = (item.get("brand") or "").lower()

    # Tier 1: Brand Status Premium
    if item_brand:
        brand_matches = [l for l in match_items if (l.get("brand") or "").lower() == item_brand]
        if len(brand_matches) >= 2:
            baseline_avg = get_clean_average(brand_matches)
            if baseline_avg is not None:
                brand_name = item.get("brand") # Use original casing for display
                baseline_msg = f"Comparable {brand_name} {display_plural} in our database"

    # Tier 2: Market-wide Fallback
    if baseline_avg is None:
        baseline_avg = get_clean_average(match_items)
        if baseline_avg is not None:
            baseline_msg = f"Comparable {display_plural} across the marketplace"

    # Global Category Fallback if Tier 1 and 2 failed
    if baseline_avg is None:
        cat_matches = [l for l in all_listings if l["category"] == item["category"] and l["id"] != item["id"]]
        baseline_avg = get_clean_average(cat_matches)
        if baseline_avg is not None:
            _, cat_plural = category_phrasing.get(item["category"], ("", "similar items"))
            baseline_msg = f"Comparable {cat_plural} across the marketplace"

    if baseline_avg is None:
        return "This item's value is unique, and we don't have enough marketplace data to evaluate price fairness yet."

    # 4. DYNAMIC FAIRNESS RATING
    item_price = item["price"]
    ratio = item_price / baseline_avg

    if ratio <= 0.8:
        rating = "a steal! 💎"
    elif ratio <= 1.2:
        rating = "fairly priced. 👍"
    else:
        rating = "expensive compared to market value. 💸"

    # 5. RETURN STRING FORMAT
    return (
        f"{display_singular} {'are' if display_singular.startswith('These') else 'is'} "
        f"priced at ${item_price:.2f}. "
        f"{baseline_msg} average around ${baseline_avg:.2f}. "
        f"We consider this price to be {rating}"
    )


# ── Tool 5: get_current_trends ───────────────────────────────────────────────

def get_current_trends() -> list[str]:
    """
    Fetch current fashion trends. Checks database first for recent trends
    (last 7 days). If none, performs a simulated google search and updates database.

    Returns:
        A list of trend strings.
    """
    from utils.data_loader import load_latest_trends, save_trends
    from datetime import datetime, timedelta

    latest = load_latest_trends()
    if latest:
        fetch_date_str, trends = latest
        # fetch_date is usually in format 'YYYY-MM-DD HH:MM:SS'
        fetch_date = datetime.strptime(fetch_date_str, "%Y-%m-%d %H:%M:%S")
        if datetime.now() - fetch_date < timedelta(days=7):
            return trends

    # If no recent trends, simulate a search and use LLM to extract trends
    client = _get_groq_client()

    # We use a system prompt that encourages the LLM to provide 'current' (2024-2025)
    # trends as if it just searched the web.
    prompt = (
        "Perform a simulated web search for 'top fashion trends 2025'. "
        "Based on your knowledge of current and forecasted trends, "
        "return a JSON list of 8-12 specific fashion trends (e.g., 'Boho Suede', 'Burgundy tones'). "
        "Return ONLY the JSON list of strings."
    )

    chat_completion = client.chat.completions.create(
        messages=[
            {
                "role": "system",
                "content": "You are a trend forecaster that returns JSON lists.",
            },
            {
                "role": "user",
                "content": prompt,
            }
        ],
        model="llama-3.3-70b-versatile",
        response_format={"type": "json_object"},
    )

    import json
    try:
        data = json.loads(chat_completion.choices[0].message.content)
        # Handle both {"trends": [...]} and [...] if the LLM is slightly off
        if isinstance(data, dict):
            trends = data.get("trends", list(data.values())[0])
        else:
            trends = data
    except Exception:
        # Fallback if parsing fails
        trends = ["Boho Chic", "Burgundy", "Denim on denim", "Animal Print", "Polo Shirts"]

    save_trends(trends)
    return trends
