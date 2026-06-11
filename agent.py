"""
agent.py

The FitFindr planning loop. Orchestrates the three tools in response to a
natural language user query, passing state between them via a session dict.

Complete tools.py and test each tool in isolation before implementing this file.

Usage (once implemented):
    from agent import run_agent
    from utils.data_loader import get_example_wardrobe

    result = run_agent(
        query="vintage graphic tee under $30, size M",
        wardrobe=get_example_wardrobe(),
    )
    print(result["fit_card"])
    print(result["error"])   # None on success
"""

import json
import os
from groq import Groq
from tools import search_listings, suggest_outfit, create_fit_card, _get_groq_client, estimate_price_fairness, get_current_trends


# ── session state ─────────────────────────────────────────────────────────────

def _new_session(query: str, wardrobe: dict) -> dict:
    """
    Initialize and return a fresh session dict for one user interaction.

    The session dict is the single source of truth for everything that happens
    during a run — it stores the original query, parsed parameters, tool results,
    and any error that caused early termination.

    You may add fields to this dict as needed for your implementation.
    """
    return {
        "query": query,              # original user query
        "parsed": {},                # extracted description / size / max_price
        "search_results": [],        # list of matching listing dicts
        "selected_item": None,       # top result, passed into suggest_outfit
        "price_analysis": None,      # string returned by estimate_price_fairness
        "wardrobe": wardrobe,        # user's wardrobe dict
        "outfit_suggestion": None,   # string returned by suggest_outfit
        "fit_card": None,            # string returned by create_fit_card
        "trend_insights": None,      # string returned by get_current_trends
        "error": None,               # set if the interaction ended early
        "modifications": [],         # track changes made to filters during retry
    }


# ── planning loop ─────────────────────────────────────────────────────────────

def _parse_query(query: str) -> dict:
    """Use LLM to extract search parameters from query."""
    client = _get_groq_client()
    prompt = (
        f"Extract search parameters from this clothing search query: \"{query}\"\n\n"
        "Return a JSON object with exactly these keys:\n"
        "- description: string (the core item description)\n"
        "- size: string or null (the size, e.g., 'M', 'W30')\n"
        "- max_price: float or null (the price limit)\n\n"
        "Return ONLY the JSON object, no other text."
    )

    chat_completion = client.chat.completions.create(
        messages=[
            {
                "role": "system",
                "content": "You are a specialized query parser that returns JSON.",
            },
            {
                "role": "user",
                "content": prompt,
            }
        ],
        model="llama-3.3-70b-versatile",
        response_format={"type": "json_object"},
    )

    return json.loads(chat_completion.choices[0].message.content)

def run_agent(query: str, wardrobe: dict) -> dict:
    """
    Main agent entry point. Runs the FitFindr planning loop for a single
    user interaction and returns the completed session dict.
    """
    # Step 1: Initialize the session
    session = _new_session(query, wardrobe)

    # Step 2: Parse the user's query
    try:
        session["parsed"] = _parse_query(query)
    except Exception as e:
        session["error"] = f"Failed to parse query: {str(e)}"
        return session

    # Step 3: Call search_listings() with Retry Logic
    description = session["parsed"].get("description", "")
    size = session["parsed"].get("size")
    max_price = session["parsed"].get("max_price")

    # Initial search
    results = search_listings(description, size, max_price)

    # Retry Loop: Style -> Price -> Size -> Brand
    # Since our search_listings handles style tags via the description query,
    # we first try loosening the description if it's too specific.

    if not results:
        # 1. Loosen Style (Assume description might be too specific)
        session["modifications"].append("broadened style keywords")
        # Simplify description to just the first two words (often category/main item)
        simple_desc = " ".join(description.split()[:2])
        results = search_listings(simple_desc, size, max_price)

        if not results:
            # 2. Loosen Price
            session["modifications"].append("removed price limit")
            results = search_listings(simple_desc, size, None)

            if not results:
                # 3. Loosen Size
                session["modifications"].append("removed size filter")
                results = search_listings(simple_desc, None, None)

    session["search_results"] = results

    if not results:
        session["error"] = f"No results found for '{description}' even after loosening filters. Try a different search!"
        return session

    # Step 4: Select the item (top result)
    session["selected_item"] = results[0]

    # Step 5: Call estimate_price_fairness()
    session["price_analysis"] = estimate_price_fairness(session["selected_item"])

    # Step 6: Call get_current_trends()
    session["trend_insights"] = get_current_trends()

    # Step 7: Call suggest_outfit()
    session["outfit_suggestion"] = suggest_outfit(session["selected_item"], wardrobe, trends=session["trend_insights"])

    # Step 8: Call create_fit_card()
    session["fit_card"] = create_fit_card(session["outfit_suggestion"], session["selected_item"])

    # Step 9: Return the session
    return session


# ── CLI test ──────────────────────────────────────────────────────────────────

if __name__ == "__main__":
    from utils.data_loader import get_example_wardrobe, get_empty_wardrobe

    print("=== Happy path: graphic tee ===\n")
    session = run_agent(
        query="looking for a vintage graphic tee under $30",
        wardrobe=get_example_wardrobe(),
    )
    if session["error"]:
        print(f"Error: {session['error']}")
    else:
        print(f"Found: {session['selected_item']['title']}")
        print(f"\nOutfit: {session['outfit_suggestion']}")
        print(f"\nFit card: {session['fit_card']}")

    print("\n\n=== No-results path ===\n")
    session2 = run_agent(
        query="designer ballgown size XXS under $5",
        wardrobe=get_example_wardrobe(),
    )
    print(f"Error message: {session2['error']}")
