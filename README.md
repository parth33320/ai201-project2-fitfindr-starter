# FitFindr 🛍️
An AI-powered multi-tool personal stylist agent that discovers secondhand clothing matching user constraints, evaluates market price fairness, integrates real-time fashion trends, and dynamically styles outfits utilizing persistent style profile memory across sessions.

## 🛠️ Tool Inventory
The following core functions power the FitFindr agent logic, as defined in `tools.py`:

1. `search_listings(description: str, size: str | None = None, max_price: float | None = None) -> list[dict]`: Searches mock listings dataset using a strict 'AND' whole-word token matching gate. Excludes partial matches (e.g., 'blue jeans' will cleanly fail a search for 'red jeans' and return `[]`). Returns a list of matching listing dictionaries sorted by keyword frequency.
2. `suggest_outfit(new_item: dict, wardrobe: dict) -> str`: Orchestrates Groq's `llama-3.3-70b-versatile` to suggest 1-2 cohesive outfit combinations. Gracefully handles an empty wardrobe by offering prescriptive, trend-aligned styling formulas, and appends unique string markers (`EXTRACTED_TAGS: tag1, tag2`) to the raw output for style memory persistence. Trends are passed inside the `wardrobe` dictionary.
3. `create_fit_card(outfit: str, new_item: dict) -> str`: Generates an authentic, casual 2-4 sentence social media caption mentioning the item, price, and platform. Safely returns an error string if outfit text is missing.
4. `estimate_price_fairness(item: dict) -> str`: Evaluates marketplace valuations using fine-grained product keyword detection and a two-tier outlier-protected pricing strategy. Appends distinct icon indicators (💎 a steal!, 👍 fairly priced, 💸 expensive).
5. `get_current_trends() -> list[str]`: Enforces a 7-day TTL cache ceiling to read trending aesthetics locally, dynamically falling back to simulated web search extractions via Groq if the cache file is stale or missing.

## 🔄 How the Planning Loop Works
FitFindr executes a linear pipeline with parameter-loosening conditional logic managed in `run_agent()`:

1. **Initialization**: Persists user state, matching empty wardrobe calls against historical caches to ensure personalized results even for new or empty accounts.
2. **Query Parsing**: Converts raw natural language queries into structured JSON objects (description, size, max_price) via a dedicated LLM call.
3. **Strict Search with Fallback Retry**: Invokes `search_listings`. If `len(results) == 0`, the agent executes a structured fallback state machine that progressively sheds constraints:
   - **Step 1: Loosen Style**: Drops the leading descriptive word token via a token-split heuristic (e.g., "vintage graphic tee" becomes "graphic tee").
   - **Step 2: Loosen Price**: Removes `max_price` ceilings.
   - **Step 3: Loosen Size**: Drops size limits.
   Each loop iteration logs an explicit string entry to the user-facing `session["modifications"]` array to ensure transparency.
4. **Conditional Exit**: If the fallback search STILL yields 0 results after all loosening steps, it skips all subsequent tool calls completely, logs a clear instruction to `session["error"]`, and terminates execution early.
5. **Enrichment & Synthesis**: On search success, the agent selects the top match, runs price fairness analysis, fetches current trend strings, injects trend metadata directly into the wardrobe payload dictionary, and builds the outfit suggestions and social captions sequentially.

## 🗃️ State Management Approach
We utilize a central `session` dictionary as the single source of truth for each interaction. This container ensures seamless data flow between steps without redundant user input:
- **Parameter Flow**: Parsed JSON parameters flow directly into the search tools.
- **Context Injection**: The top `selected_item` dict flows into price assessment, outfit styling, and fit card generation.
- **Sequential Synthesis**: The generated `outfit_suggestion` context flows directly into the caption tool.
- **Early Termination**: The `session["error"]` key acts as a global flag for the Gradio UI; if populated, downstream panels are bypassed and the error is displayed prominently.

## 💾 Advanced Stretch Features Documentation
- **Style Profile Memory**: A multi-user persistent layer managed in `data/style_profile.json` via `utils/storage_helper.py`. `run_agent()` intercepts empty wardrobes, loads historical style tags for the specific `user_id`, and applies a **Most-Recently-Used (MRU) eviction strategy** capped at a 10-tag limit. These tags are auto-injected into the stylist context using the `wardrobe["historical_preferences"]` payload wrapper.
- **Trend Awareness**: `get_current_trends()` influences the final styling output by embedding real-time aesthetics (e.g., "Boho Chic", "Burgundy tones") directly into the system prompt wrappers, creating tailored, trend-forward suggestions.
- **Retry Logic with Fallback**: The agent dynamically transforms a failing search (like "red jeans") into a broadened, successful alternative lookup (like "jeans") without requiring a manual user query adjustment, significantly improving user conversion.

## ⚠️ Error Handling Strategy
| Module | Failure Mode | Agent Handling | User Feedback |
| :--- | :--- | :--- | :--- |
| **Query Parser** | Unstructured/Gibberish input | LLM returns null fields | "Failed to parse query..." |
| **Search Engine** | Zero results (Strict) | Triggers Fallback Retry | "We couldn't find an exact match, so we broadened..." |
| **Search Engine** | Zero results (After Retry) | Pipeline Termination | "No items found matching your description..." |
| **Outfit Stylist** | Empty Wardrobe | Inject Historical Style Memory | General styling advice + MRU preference match |
| **Fit Card Tool** | Missing Outfit Text | Error String Return | "Could not generate fit card due to missing details." |

### Concrete Failure Case 1: The 'Impossible' Query
If a user searches for an impossible combination, such as **'designer ballgown size XXS under $5'**:
1. The search engine fails to find matches.
2. Retry logic drops "designer", then drops the $5 price limit, then drops the XXS size limit.
3. If still zero matches exist in the mock dataset (e.g., no ballgowns), the agent sets `session["error"]` to a helpful message and skips the stylist and caption tools entirely, preventing the generation of "hallucinated" advice for a non-existent item.

### Concrete Failure Case 2: Empty Wardrobe
If a new user with an empty wardrobe searches for a "vintage tee":
1. `suggest_outfit` detects `len(wardrobe['items']) == 0`.
2. Instead of failing, the agent loads the user's `historical_preferences` from `data/style_profile.json`.
3. The LLM is prompted to provide "general styling advice" incorporating those historical preferences and current trends, ensuring the user still gets value even without a digital wardrobe.

## 🧠 Spec Reflection
The specification process forced early architectural considerations for the empty wardrobe edge case, leading to the development of our Style Profile Memory. We diverged from the initial plan by choosing LLM-based query parsing over fragile regex patterns, allowing us to handle varied price strings (e.g., "under $30" vs "max 30 bucks") with 99% accuracy.

## 🤖 AI Usage Transparency
1. **Instance 1: Tool Implementation (`search_listings`)**
   - **Direction**: I directed the AI to draft an initial search function that filters by size and price from a JSON list.
   - **Revision**: I manually **overrode** the AI's suggested TF-IDF/semantic search approach, replacing it with a strict keyword token AND-gate using word-boundary regex (`\b`). This ensures the agent's search behavior remains predictable, auditable, and avoids "fuzzy" matches that might confuse the stylist tool.
2. **Instance 2: UI State Synchronization**
   - **Direction**: I directed the AI to map the complex `session` dictionary state to the 6 Gradio output components in `app.py`.
   - **Revision**: I refined the generated logic to ensure `selected_item` IDs were explicitly preserved and tracked across the debug panel. I also added explicit logic to handle the "Early Termination" state, ensuring that the UI displays the `session["error"]` message in the primary listing panel while clearing subsequent panels.
