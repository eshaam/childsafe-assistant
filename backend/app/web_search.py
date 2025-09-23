# app/web_search.py

import os  # Standard library for environment variables
from serpapi import GoogleSearch  # Google search API client (via SerpAPI)

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
    tavily = TavilyClient(api_key=os.getenv("TAVILY_API_KEY"))
    results = tavily.search(query, max_results=max_results)

    if not results.get("results"):
        return {"query": query, "answer": "No relevant articles found.", "articles": []}

    # Filter strictly for ChildSafe South Africa mentions
    childsafe_results = [
        r for r in results["results"]
        if "childsafe" in (r.get("title", "") + r.get("content", "")).lower()
    ]

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
    Search the web using Google (via SerpAPI).
    Returns only ChildSafe South Africa related content.
    """
    try:
        search = GoogleSearch({
            "q": query,
            "api_key": os.getenv("SERPAPI_API_KEY"),
            "num": max_results,
        })
        results = search.get_dict()

        if "organic_results" not in results:
            return {"query": query, "answer": "No search results found.", "articles": []}

        # Slice top N results
        articles = results["organic_results"][:max_results]

        # Filter strictly for ChildSafe South Africa
        childsafe_articles = [
            a for a in articles
            if "childsafe" in (a.get("title", "") + a.get("snippet", "")).lower()
        ]

        if not childsafe_articles:
            return {
                "query": query,
                "articles": [],
                "answer": "No relevant ChildSafe South Africa information found.",
            }

        # Build formatted answer
        answer_parts = []
        for article in childsafe_articles:
            title = article.get("title", "Untitled")
            link = article.get("link", "")
            snippet = article.get("snippet", "")
            answer_parts.append(f"**{title}**\n{snippet}\n[Read more]({link})")

        answer = "\n\n".join(answer_parts)

        return {"query": query, "articles": childsafe_articles, "answer": answer}

    except Exception as e:
        return {
            "query": query,
            "articles": [],
            "answer": f"Search error: {str(e)}",
        }

# -----------------------------------------------------------------------------
# SEARCH DISPATCHER
# -----------------------------------------------------------------------------

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
