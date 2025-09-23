# app/web_search.py

import os  # Standard library for environment variables
import serpapi  # Google search API client (via SerpAPI)

# -----------------------------------------------------------------------------
# SEARCH MODE CONFIG
# -----------------------------------------------------------------------------

# Preferred search mode: "tavily" or "google"
SEARCH_MODE = os.getenv("SEARCH_MODE", "tavily").lower()

# Try to import Tavily client if selected
if SEARCH_MODE == "tavily":
    try:
        from tavily import TavilyClient
    except ImportError:
        # If Tavily is unavailable, fallback to Google
        SEARCH_MODE = "google"

# -----------------------------------------------------------------------------
# TAVILY SEARCH
# -----------------------------------------------------------------------------

def tavily_search(query: str, max_results: int = 5):
    """
    Search the web using Tavily API.
    Returns only ChildSafe South Africa related content.
    """
    # Enhance query with ChildSafe South Africa context if not already present
    enhanced_query = query
    if "childsafe" not in query.lower() and "child safe" not in query.lower():
        enhanced_query = f"{query} ChildSafe South Africa child safety"

    tavily = TavilyClient(api_key=os.getenv("TAVILY_API_KEY"))
    results = tavily.search(enhanced_query, max_results=max_results)

    if not results.get("results"):
        return {"query": query, "answer": "No relevant articles found.", "articles": []}

    # Filter for ChildSafe South Africa related content
    childsafe_keywords = ["childsafe", "child safe", "child safety", "children's safety", "child protection", "south africa child"]

    def is_childsafe_related(result):
        text = (result.get("title", "") + " " + result.get("content", "")).lower()
        return any(keyword in text for keyword in childsafe_keywords)

    childsafe_results = [r for r in results["results"] if is_childsafe_related(r)]

    if not childsafe_results:
        return {
            "query": query,
            "articles": [],
            "answer": "No relevant ChildSafe South Africa information found.",
        }

    # Build formatted answer
    answer_parts = []
    for r in childsafe_results:
        title = r.get("title", "Untitled")
        url = r.get("url", "")
        content = r.get("content", "")
        snippet = content[:200]
        answer_parts.append(f"**{title}**\n{snippet}...\n[Read more]({url})")

    answer = "\n\n".join(answer_parts)

    return {"query": query, "articles": childsafe_results, "answer": answer}

# -----------------------------------------------------------------------------
# GOOGLE SEARCH (via SerpAPI)
# -----------------------------------------------------------------------------

def google_search(query: str, max_results: int = 5):
    """
    Search the web using SerpApi (compatible with serpapi>=0.1.5).
    Returns only ChildSafe South Africa related content.
    """
    import os

    # Enhance query with ChildSafe South Africa context if not present
    enhanced_query = query
    if "childsafe" not in query.lower() and "child safe" not in query.lower():
        enhanced_query = f"{query} ChildSafe South Africa child safety"

    api_key = os.getenv("SERPAPI_API_KEY")
    if not api_key:
        return {"query": query, "articles": [], "answer": "No SERPAPI_API_KEY configured."}

    # Try the new serpapi package (>=0.1.5)
    results = None
    search_error = None
    try:
        import serpapi
        client = serpapi.Client(api_key=api_key)
        params = {
            "engine": "google",
            "q": enhanced_query,
            "hl": "en",
            "gl": "za",        # bias to South Africa
            "num": max_results,
        }
        results = client.search(params)  # SerpResults (dict-like)
    except Exception as e:
        search_error = e
        # Fallbacks for older/alternate wrappers (best-effort)
        try:
            # try the legacy google-search-results package interface
            from google_search_results import GoogleSearch  # package name on PyPI is google-search-results
            gs = GoogleSearch({"q": enhanced_query, "api_key": api_key, "num": max_results})
            results = gs.get_dict()
        except Exception:
            try:
                # another possible legacy import (some older installs expose this)
                from serpapi import GoogleSearch
                gs = GoogleSearch({"q": enhanced_query, "api_key": api_key, "num": max_results})
                results = gs.get_dict()
            except Exception as e2:
                # return helpful debug message (both exceptions)
                return {
                    "query": query,
                    "articles": [],
                    "answer": f"Search error: {search_error} / {e2}"
                }

    # Normalize results: results should be dict-like with "organic_results"
    if not results:
        return {"query": query, "articles": [], "answer": "No search results found.",}

    # results may be a SerpResults object (behaves like dict)
    try:
        organic = results.get("organic_results") if hasattr(results, "get") else results["organic_results"]
    except Exception:
        organic = None

    if not organic:
        return {"query": query, "articles": [], "answer": "No organic results found.",}

    # Take top N results
    articles = organic[:max_results]

    # Filter for ChildSafe-related content
    childsafe_keywords = [
        "childsafe", "child safe", "child safety", "children's safety",
        "child protection", "south africa child"
    ]

    def is_childsafe_related(item):
        # item is usually a dict with 'title' and 'snippet'
        title = item.get("title", "") if isinstance(item, dict) else ""
        snippet = item.get("snippet", "") if isinstance(item, dict) else ""
        text = f"{title} {snippet}".lower()
        return any(k in text for k in childsafe_keywords)

    childsafe_articles = [a for a in articles if is_childsafe_related(a)]

    if not childsafe_articles:
        return {
            "query": query,
            "articles": [],
            "answer": "No relevant ChildSafe South Africa information found.",
        }

    # Build formatted answer
    answer_parts = []
    out_articles = []
    for r in childsafe_articles:
        title = r.get("title", "Untitled") if isinstance(r, dict) else ""
        link = r.get("link") or r.get("displayed_link") or r.get("source") or ""
        snippet = r.get("snippet", "") if isinstance(r, dict) else ""
        answer_parts.append(f"**{title}**\n{snippet}\n[Read more]({link})")
        out_articles.append(r)

    answer = "\n\n".join(answer_parts)

    return {"query": query, "articles": out_articles, "answer": answer}

def search_articles(query: str, max_results: int = 5):
    """
    Dispatch search to Tavily or Google depending on config & API keys.
    - If Tavily enabled and API key exists → use Tavily.
    - Else if Google enabled and API key exists → use Google.
    - Else return error.
    """
    # Case 1: Google explicitly selected and API key provided
    if SEARCH_MODE == "google" and os.getenv("SERPAPI_API_KEY"):
        return google_search(query, max_results)

    # Case 2: Tavily selected and API key provided
    if SEARCH_MODE == "tavily" and os.getenv("TAVILY_API_KEY"):
        return tavily_search(query, max_results)

    # Case 3: No valid provider configured
    return {
        "query": query,
        "articles": [],
        "answer": "No search API keys configured. Please set SERPAPI_API_KEY or TAVILY_API_KEY.",
    }
