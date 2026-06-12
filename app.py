"""
app.py

Gradio interface for FitFindr. The layout and wiring are already set up —
your job is to fill in handle_query() so it calls run_agent() and maps
the session results to the three output panels.

Run with:
    python app.py

Then open the localhost URL shown in your terminal (usually http://localhost:7860,
but check your terminal — the port may differ).
"""

import os
import gradio as gr

from agent import run_agent
from utils.data_loader import get_example_wardrobe, get_empty_wardrobe


# ── query handler ─────────────────────────────────────────────────────────────

from utils.data_loader import save_wardrobe, load_wardrobe

def handle_query(user_query: str, wardrobe_choice: str, user_id: str = "default_user") -> tuple[str, str, str, str, str, dict]:
    """
    Called by Gradio when the user submits a query.
    """
    if not user_query or not user_query.strip():
        return "Please enter a search query.", "", "", "", "", {}

    # Persistent wardrobe logic
    wardrobe = load_wardrobe(user_id)
    if not wardrobe or wardrobe_choice == "Reset to Example":
        wardrobe = get_example_wardrobe()
        save_wardrobe(user_id, wardrobe)
    elif wardrobe_choice == "Reset to Empty":
        wardrobe = get_empty_wardrobe()
        save_wardrobe(user_id, wardrobe)

    session = run_agent(user_query, wardrobe)

    if session["error"]:
        return session["error"], "", "", "", "", session

    item = session["selected_item"]

    mod_text = ""
    if session["modifications"]:
        mod_text = f"⚠️ Note: We couldn't find an exact match, so we {', '.join(session['modifications'])} to find this for you!\n\n"

    listing_text = (
        f"{mod_text}"
        f"Title: {item['title']}\n"
        f"Price: ${item['price']}\n"
        f"Platform: {item['platform']}\n"
        f"Size: {item['size']}\n"
        f"Condition: {item['condition']}\n"
        f"Description: {item['description']}"
    )

    trend_text = "Current Fashion Trends:\n- " + "\n- ".join(session["trend_insights"][:5])

    return listing_text, session["price_analysis"], session["outfit_suggestion"], trend_text, session["fit_card"], session


# ── interface ─────────────────────────────────────────────────────────────────

EXAMPLE_QUERIES = [
    "vintage graphic tee under $30",
    "90s track jacket in size M",
    "flowy midi skirt under $40",
    "black combat boots size 8",
    "designer ballgown size XXS under $5",   # deliberate no-results test
]

def build_interface():
    with gr.Blocks(title="FitFindr") as demo:
        gr.Markdown("""
# FitFindr 🛍️
Find secondhand pieces and get outfit ideas based on your wardrobe.
Describe what you're looking for — include size and price if you want to filter.
        """)

        with gr.Row():
            with gr.Column(scale=3):
                query_input = gr.Textbox(
                    label="What are you looking for?",
                    placeholder="e.g. vintage graphic tee under $30, size M",
                    lines=2,
                )
            with gr.Column(scale=1):
                user_id = gr.Textbox(label="User ID (for style memory)", value="default_user")
                wardrobe_choice = gr.Radio(
                    choices=["Use Saved", "Reset to Example", "Reset to Empty"],
                    value="Use Saved",
                    label="Wardrobe Management",
                )

        submit_btn = gr.Button("Find it", variant="primary")

        with gr.Row():
            listing_output = gr.Textbox(
                label="🛍️ Top listing found",
                lines=10,
                interactive=False,
            )
            price_output = gr.Textbox(
                label="💰 Price Analysis",
                lines=10,
                interactive=False,
            )

        with gr.Row():
            outfit_output = gr.Textbox(
                label="👗 Outfit idea",
                lines=10,
                interactive=False,
            )
            trend_output = gr.Textbox(
                label="📈 Trend Insights",
                lines=10,
                interactive=False,
            )

        with gr.Row():
            fitcard_output = gr.Textbox(
                label="✨ Your fit card",
                lines=5,
                interactive=False,
            )

        show_debug = os.environ.get("FITFINDR_DEBUG", "false").lower() == "true"
        with gr.Row(visible=show_debug):
            debug_panel = gr.JSON(
                label="🛠️ Session Log / Debug Panel (Internal State)",
            )

        gr.Examples(
            examples=[[q, "Use Saved", "default_user"] for q in EXAMPLE_QUERIES],
            inputs=[query_input, wardrobe_choice, user_id],
            label="Try these queries",
        )

        submit_btn.click(
            fn=handle_query,
            inputs=[query_input, wardrobe_choice, user_id],
            outputs=[listing_output, price_output, outfit_output, trend_output, fitcard_output, debug_panel],
        )
        query_input.submit(
            fn=handle_query,
            inputs=[query_input, wardrobe_choice, user_id],
            outputs=[listing_output, price_output, outfit_output, trend_output, fitcard_output, debug_panel],
        )

    return demo


if __name__ == "__main__":
    demo = build_interface()
    demo.launch()
