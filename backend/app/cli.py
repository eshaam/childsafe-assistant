# app/cli.py

import os  # Standard library for env vars
from pathlib import Path  # For filesystem-safe paths
import requests  # To download PDF reports from URLs
import click  # For building CLI commands
import chromadb  # Vector database client
from PyPDF2 import PdfReader  # PDF text extraction
from dotenv import load_dotenv  # Load .env configuration
from langchain.text_splitter import RecursiveCharacterTextSplitter  # Smart text chunking

# -----------------------------------------------------------------------------
# CONFIGURATION
# -----------------------------------------------------------------------------

# Load environment variables into process
load_dotenv()

# Define a consistent "data" directory to store downloaded PDFs
DATA_DIR = Path(__file__).resolve().parent.parent / "data"
DATA_DIR.mkdir(exist_ok=True)  # Ensure directory exists

# ChromaDB connection details
CHROMA_HOST = os.getenv("CHROMA_HOST", "http://localhost:8000")
COLLECTION_NAME = os.getenv("COLLECTION_NAME", "childsafe_reports")

# Registry of ChildSafe annual reports (year -> URL)
REPORTS = {
    "2005-2006": "https://childsafe.org.za/downloads/annual_report2005_2006.pdf",
    "2006-2007": "https://childsafe.org.za/downloads/Annual_Report_2006-2007.pdf",
    "2011": "https://childsafe.org.za/downloads/annual_report2012.pdf",
    "2017-2018": "https://childsafe.org.za/downloads/Annual-Report-2017-2018.pdf",
    "2018-2019": "https://childsafe.org.za/downloads/childsafe-annual-report-2019.pdf",
    "2019-2020": "https://childsafe.org.za/downloads/ChildSafe-Annual-Report-2019-20082020.pdf",
    "2020-2021": "https://childsafe.org.za/downloads/Annual-Report-01Oct2021.pdf",
    "2021-2022": "https://childsafe.org.za/downloads/Annual%20Report%202021-2022.pdf",
    "2022-2023": "https://childsafe.org.za/wp-content/uploads/2023/10/Annual%20Report%202022-2023%20Presentation%20Final%20.pptx",
}

# -----------------------------------------------------------------------------
# CLI ENTRYPOINT
# -----------------------------------------------------------------------------

@click.group()
def cli():
    """ChildSafe Data Ingestion CLI"""
    pass  # Acts as a parent group for commands


# -----------------------------------------------------------------------------
# DOWNLOAD COMMAND
# -----------------------------------------------------------------------------

@cli.command()
@click.option(
    "--report",
    default="all",
    help="Which report to download (year) or 'all' to download everything",
)
def download(report: str):
    """
    Download one or more ChildSafe annual reports into the local data directory.
    """
    # Decide whether to fetch all or a single report
    if report == "all":
        items = REPORTS.items()
    else:
        if report not in REPORTS:
            raise click.ClickException(f"Report {report} not found")
        items = [(report, REPORTS[report])]

    # Download each report and write to disk
    for year, url in items:
        out_path = DATA_DIR / f"{year}{Path(url).suffix}"
        click.echo(f"Downloading {year} -> {out_path}")

        r = requests.get(url)  # Fetch file from the internet
        r.raise_for_status()  # Fail if HTTP error
        out_path.write_bytes(r.content)  # Save to disk


# -----------------------------------------------------------------------------
# CHUNK + POST COMMAND
# -----------------------------------------------------------------------------

@cli.command()
@click.option("--chunk-size", default=800, help="Max size of text chunks (chars)")
@click.option("--chunk-overlap", default=50, help="Overlap between chunks (chars)")
def chunk_and_post(chunk_size: int, chunk_overlap: int):
    """
    Rebuild ChromaDB collection from local PDFs:
    1. Clear old collection.
    2. Split PDFs into chunks using LangChain Recursive splitter.
    3. Upload chunks into Chroma vector database.
    """

    try:
        # Connect to ChromaDB server
        client = chromadb.HttpClient(host=CHROMA_HOST)

        # Reset existing collection if it exists
        if COLLECTION_NAME in [c.name for c in client.list_collections()]:
            print(f"Deleting existing collection '{COLLECTION_NAME}'...")
            client.delete_collection(name=COLLECTION_NAME)

        # Create new collection fresh
        print(f"Creating new collection '{COLLECTION_NAME}'...")
        collection = client.create_collection(name=COLLECTION_NAME)

        total_chunks = 0

        # Define splitter (LangChain standard)
        splitter = RecursiveCharacterTextSplitter(
            chunk_size=chunk_size,
            chunk_overlap=chunk_overlap,
            length_function=len,  # Count characters
            separators=["\n\n", "\n", ".", " ", ""],  # Fallback splitting hierarchy
        )

        # Process each PDF in local data directory
        for pdf_path in DATA_DIR.glob("*.pdf"):
            print(f"Processing {pdf_path}")

            # Use filename stem as report identifier (e.g., "2019-2020")
            report_year = pdf_path.stem

            reader = PdfReader(pdf_path)
            for i, page in enumerate(reader.pages):
                text = page.extract_text()

                # Skip empty or very short pages
                if not text or len(text.strip()) < 50:
                    continue

                # Split page into chunks
                chunks = splitter.split_text(text)

                # Add each chunk to ChromaDB
                for j, chunk in enumerate(chunks):
                    if len(chunk.strip()) < 50:
                        continue

                    # Build unique chunk ID: year-page-chunk
                    doc_id = f"{report_year}-{i}-{j}"

                    # Insert into ChromaDB
                    collection.add(
                        ids=[doc_id],
                        documents=[chunk],
                        metadatas=[
                            {
                                "source": str(pdf_path),      # File path
                                "report_year": report_year,   # Year identifier
                                "page": i,                    # Page number
                                "chunk_size": len(chunk),     # Chunk length
                                "chunk_index": j,             # Chunk order in page
                            }
                        ],
                    )
                    total_chunks += 1

        # Report ingestion results
        final_count = collection.count()
        print("✅ Chunking and upload complete!")
        print(f"Total chunks added: {total_chunks}")
        print(f"Total documents in collection: {final_count}")

    except Exception as e:
        print(f"❌ Error during chunking: {e}")
        raise


# -----------------------------------------------------------------------------
# MAIN
# -----------------------------------------------------------------------------

if __name__ == "__main__":
    cli()  # Entrypoint for CLI
