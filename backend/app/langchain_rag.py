# app/langchain_rag.py

import os  # Standard library for env vars
import chromadb  # Vector DB client for local RAG
from langchain.prompts import PromptTemplate  # For structured prompting
from langchain_google_genai import ChatGoogleGenerativeAI  # Gemini LLM wrapper
from langchain_core.output_parsers import StrOutputParser  # Extract string outputs
from tavily import TavilyClient  # Web search API client (alternative to SerpAPI)
from app.cli import COLLECTION_NAME, CHROMA_HOST  # Config shared with CLI
from app.web_search import search_articles  # External search helper

# -----------------------------------------------------------------------------
# LLM INITIALIZATION
# -----------------------------------------------------------------------------

# Initialize Google Gemini model (via LangChain wrapper)
llm = ChatGoogleGenerativeAI(
    model="models/gemini-2.5-flash",          # LLM model
    google_api_key=os.getenv("GOOGLE_API_KEY"),  # Auth token
    temperature=0.2,  # Low temperature = more factual, less creative
    max_retries=0     # Fail fast if request errors
)

# Initialize Tavily client (for web retrieval)
tavily = TavilyClient(api_key=os.getenv("TAVILY_API_KEY"))

# -----------------------------------------------------------------------------
# PROMPT TEMPLATES
# -----------------------------------------------------------------------------

# 1. Intent classification: decide if query is about ChildSafe (local) or general info (web)
intent_template = PromptTemplate(
    input_variables=["query"],
    template="""Classify the user query as local or web.

User query: {query}

Return exactly one word:
- "local" if the query is about ChildSafe South Africa, their programs, annual reports, road safety, child safety initiatives, financial performance or any information that would be found in ChildSafe's annual reports
- "web" if the query is asking for general news, current events, articles.

Examples:
"who is childsafe" -> local
"childsafe programs" -> local
"road safety statistics" -> local
"latest news" -> web
"current events" -> web
"financial" -> local
"""
)

# 2. Query rewriting: improve phrasing for better document search
rewrite_template = PromptTemplate(
    input_variables=["query"],
    template="Rewrite this query to be more precise for document search:\n\n{query}\n\nRewritten:"
)

# 3. Answer synthesis (local mode): ground answer in retrieved ChildSafe documents
answer_template = PromptTemplate(
    input_variables=["query", "docs"],
    template="""You are an assistant answering strictly from ChildSafe South Africa annual reports.  

User Question: {query}  

Relevant Passages from Reports:
{docs}  

Instructions:
- Only answer using the provided passages.  
- If the information is not in the passages, say:  
  "No relevant information found in ChildSafe reports."  
- Always cite the report year and page number like this:  
  "According to the 2019–2020 report (page 5)...".  
- Never use outside knowledge or speculation.  
- Never include information unrelated to ChildSafe South Africa.  
"""
)

# 4. Answer synthesis (web mode): summarize external articles but filter for ChildSafe relevance
summary_template = PromptTemplate(
    input_variables=["query", "articles"],
    template="""You are an assistant summarizing external web articles about **ChildSafe South Africa**.  

User Request: {query}  

Articles:  
{articles}  

Instructions:
- Only summarize content explicitly mentioning **ChildSafe South Africa (https://childsafe.org.za/)**.  
- Ignore all other content completely.  
- If no articles mention ChildSafe South Africa, respond with:  
  "No relevant ChildSafe South Africa information found."  
- For valid articles, write 2–3 bullet points each.  
- Always include the article link.  
- Do not speculate, invent details, or include unrelated information.  
"""
)

# -----------------------------------------------------------------------------
# SMART QUERY ORCHESTRATOR
# -----------------------------------------------------------------------------

def smart_query(query: str, top_k: int = 5):
    """
    Orchestrates the ChildSafe RAG pipeline:
    1. Classify query intent (local vs web).
    2. If "web": search external articles → summarize.
    3. If "local": query ChromaDB (ChildSafe reports) → summarize.
    Adds runtime safeguards to ensure answers are strictly ChildSafe-only.
    """

    # ---------------------------------------------------------
    # STEP 1: INTENT DETECTION
    # ---------------------------------------------------------
    # Build chain: intent_template → Gemini LLM → string output
    intent = (
        intent_template
        | llm
        | StrOutputParser()
    ).invoke({"query": query}).strip().lower()  # Normalize result ("local" or "web")

    # ---------------------------------------------------------
    # STEP 2: WEB MODE (external retrieval + summarization)
    # ---------------------------------------------------------
    if intent == "web":
        # Call web search helper (Tavily/Google depending on config)
        results = search_articles(query, max_results=5)

        # If no articles returned, fail fast with strict fallback
        if not results.get("articles"):
            return {
                "query": query,
                "mode": "web",
                "answer": "No relevant ChildSafe South Africa information found.",
                "articles": [],
            }

        # Extract the raw articles
        articles = results["articles"]

        # Format articles into structured text for the LLM
        formatted = []
        for r in articles:
            title = r.get("title", "Untitled")  # Use title if available
            url = r.get("link", r.get("url", ""))  # Normalize URL key
            snippet = r.get("snippet", r.get("content", ""))[:300]  # Limit snippet length
            formatted.append(f"- Title: {title}\n  URL: {url}\n  Content: {snippet}...")
        articles_text = "\n\n".join(formatted)  # Join into block string

        # Summarize using Gemini + summary prompt
        answer = (
            summary_template
            | llm
            | StrOutputParser()
        ).invoke({
            "query": query,
            "articles": articles_text,
        })

        # ✅ Runtime safeguard:
        # If Gemini answer does not mention ChildSafe, override with strict fallback
        if "childsafe" not in answer.lower():
            return {
                "query": query,
                "mode": "web",
                "answer": "No relevant ChildSafe South Africa information found.",
                "articles": [],
            }

        # Otherwise return valid structured response
        return {
            "query": query,
            "mode": "web",
            "answer": answer,
            "articles": articles,
        }

    # ---------------------------------------------------------
    # STEP 3: LOCAL MODE (RAG over ChromaDB)
    # ---------------------------------------------------------
    else:
        # Rewrite query for better document retrieval
        rewritten = (
            rewrite_template
            | llm
            | StrOutputParser()
        ).invoke({"query": query})

        # Connect to ChromaDB server and open collection
        client = chromadb.HttpClient(host=CHROMA_HOST)
        collection = client.get_collection(COLLECTION_NAME)

        # Query Chroma for top_k relevant chunks
        results = collection.query(query_texts=[rewritten], n_results=top_k)
        documents = results.get("documents", [[]])[0]  # Extract docs
        metadatas = results.get("metadatas", [[]])[0]  # Extract metadata

        # If no docs found, return strict fallback
        if not documents:
            return {
                "query": query,
                "mode": "local",
                "answer": "No relevant information found in ChildSafe reports.",
            }

        # Build context for Gemini summarization
        context_blocks = []
        for doc, meta in zip(documents, metadatas):
            source = meta.get("report_year", "unknown report")  # Year metadata
            page = meta.get("page", "?")  # Page metadata
            context_blocks.append(f"[Report: {source}, Page {page}]\n{doc}")  # Annotated chunk
        context = "\n\n".join(context_blocks)

        # Summarize using Gemini + answer prompt
        answer = (
            answer_template
            | llm
            | StrOutputParser()
        ).invoke({
            "query": query,
            "docs": context,
        })

        # ✅ Runtime safeguard:
        # If Gemini does not reference "ChildSafe" or "report", override with fallback
        if "childsafe" not in answer.lower() and "report" not in answer.lower():
            return {
                "query": query,
                "mode": "local",
                "rewritten": rewritten,
                "answer": "No relevant information found in ChildSafe reports.",
                "documents": documents,
                "metadatas": metadatas,
            }

        # Otherwise return valid structured response
        return {
            "query": query,
            "mode": "local",
            "rewritten": rewritten,
            "answer": answer,
            "documents": documents,
            "metadatas": metadatas,
        }
