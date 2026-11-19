
import re
import requests
import fitz

from urllib.parse import quote


OPENALEX_URL = "https://api.openalex.org/works/"


STOP_WORDS = {
    "the", "and", "for", "with", "that", "this", "from",
    "were", "was", "are", "is", "has", "have", "had",
    "been", "being", "into", "than", "then", "they",
    "their", "them", "which", "while", "where", "when",
    "what", "who", "whom", "whose", "will", "would",
    "could", "should", "can", "may", "might", "also",
    "such", "these", "those", "our", "using", "used",
    "use", "based", "between", "among", "within",
    "through", "study", "research", "paper"
}


def clean_doi(doi):
    if not doi:
        return None

    doi = str(doi).strip()

    doi = re.sub(
        r"^https?://(dx\.)?doi\.org/",
        "",
        doi,
        flags=re.IGNORECASE
    )

    doi = doi.strip()

    return doi or None


def tokenize(text):
    words = re.findall(
        r"\b[a-zA-Z0-9]+\b",
        str(text).lower()
    )

    return {
        word for word in words
        if len(word) > 2 and word not in STOP_WORDS
    }


def calculate_relevance(claim, passage):
    claim_words = tokenize(claim)
    passage_words = tokenize(passage)

    if not claim_words or not passage_words:
        return 0.0

    overlap = claim_words.intersection(passage_words)

    score = len(overlap) / len(claim_words)

    return round(score, 3)


def find_open_access_pdf(doi):
    """
    Uses OpenAlex to find an openly accessible
    PDF for a publication identified by DOI.
    """

    encoded_doi = quote(
        "https://doi.org/" + doi,
        safe=""
    )

    response = requests.get(
        OPENALEX_URL + encoded_doi,
        headers={
            "User-Agent": "CiteVerifyAI/1.0"
        },
        timeout=20
    )

    if response.status_code == 404:
        return {
            "success": False,
            "status": "publication_not_found",
            "error": "Publication was not found in OpenAlex"
        }

    response.raise_for_status()

    work = response.json()

    locations = work.get("locations", [])

    best_location = work.get("best_oa_location") or {}

    pdf_url = best_location.get("pdf_url")

    landing_page_url = best_location.get("landing_page_url")

    if not pdf_url:
        for location in locations:
            if location.get("pdf_url"):
                pdf_url = location["pdf_url"]
                landing_page_url = location.get(
                    "landing_page_url"
                )
                break

    if not pdf_url:
        return {
            "success": False,
            "status": "no_open_access_pdf",
            "title": work.get("title"),
            "landing_page_url": landing_page_url,
            "error": "No openly accessible PDF was found"
        }

    return {
        "success": True,
        "status": "open_access_pdf_found",
        "title": work.get("title"),
        "pdf_url": pdf_url,
        "landing_page_url": landing_page_url
    }


def download_pdf(pdf_url):
    response = requests.get(
        pdf_url,
        headers={
            "User-Agent": "CiteVerifyAI/1.0"
        },
        timeout=30,
        stream=True
    )

    response.raise_for_status()

    content_length = response.headers.get("Content-Length")

    if content_length and int(content_length) > 20 * 1024 * 1024:
        raise ValueError("Research PDF exceeds the 20 MB download limit")

    chunks = []
    total_size = 0

    for chunk in response.iter_content(chunk_size=8192):
        if not chunk:
            continue

        total_size += len(chunk)

        if total_size > 20 * 1024 * 1024:
            raise ValueError("Research PDF exceeds the 20 MB download limit")

        chunks.append(chunk)

    pdf_bytes = b"".join(chunks)

    if not pdf_bytes.startswith(b"%PDF"):
        raise ValueError("The retrieved URL did not return a valid PDF")

    return pdf_bytes


def extract_pdf_passages(pdf_bytes, claim, max_results=5):
    """
    Extracts sentences from a PDF and ranks them
    by lexical overlap with the research claim.

    Relevance is not proof of scientific support.
    """

    document = fitz.open(
        stream=pdf_bytes,
        filetype="pdf"
    )

    candidates = []

    try:
        for page_number, page in enumerate(document, start=1):

            page_text = page.get_text("text")

            sentences = re.split(
                r"(?<=[.!?])\s+",
                page_text
            )

            for sentence in sentences:

                sentence = re.sub(
                    r"\s+",
                    " ",
                    sentence
                ).strip()

                if len(sentence) < 40:
                    continue

                if len(sentence) > 1200:
                    continue

                score = calculate_relevance(
                    claim,
                    sentence
                )

                if score <= 0:
                    continue

                candidates.append({
                    "page": page_number,
                    "passage": sentence,
                    "relevance_score": score
                })

    finally:
        document.close()

    candidates.sort(
        key=lambda item: item["relevance_score"],
        reverse=True
    )

    # Remove duplicate passages.
    unique_passages = []
    seen = set()

    for item in candidates:

        normalized = item["passage"].lower()

        if normalized in seen:
            continue

        seen.add(normalized)
        unique_passages.append(item)

        if len(unique_passages) >= max_results:
            break

    return unique_passages


def retrieve_evidence(claim, publication):
    """
    Retrieves an open-access publication PDF
    and extracts potentially relevant passages.

    This does not determine whether a claim is true.
    """

    try:
        if not isinstance(publication, dict):
            return {
                "success": False,
                "status": "invalid_publication",
                "error": "Publication metadata must be an object"
            }

        doi = clean_doi(publication.get("doi"))

        if not doi:
            return {
                "success": False,
                "status": "missing_doi",
                "error": "A DOI is required for this retrieval method"
            }

        source = find_open_access_pdf(doi)

        if not source.get("success"):
            return {
                "success": False,
                "status": source.get("status"),
                "publication_title": source.get("title"),
                "source_url": source.get("landing_page_url"),
                "error": source.get("error"),
                "verification_status": "not_verified"
            }

        pdf_bytes = download_pdf(source["pdf_url"])

        passages = extract_pdf_passages(
            pdf_bytes,
            claim
        )

        if not passages:
            return {
                "success": True,
                "status": "pdf_retrieved_no_relevant_passages",
                "publication_title": source.get("title"),
                "doi": doi,
                "pdf_url": source["pdf_url"],
                "landing_page_url": source.get("landing_page_url"),
                "passages": [],
                "verification_status": "not_verified",
                "message": "PDF retrieved, but no sufficiently relevant passages were found"
            }

        return {
            "success": True,
            "status": "evidence_passages_found",
            "publication_title": source.get("title"),
            "doi": doi,
            "pdf_url": source["pdf_url"],
            "landing_page_url": source.get("landing_page_url"),
            "total_passages": len(passages),
            "passages": passages,
            "verification_status": "not_verified",
            "message": "Potentially relevant passages retrieved. Scientific support has not been established."
        }

    except requests.exceptions.Timeout:
        return {
            "success": False,
            "status": "timeout",
            "error": "The research source request timed out"
        }

    except requests.exceptions.RequestException as error:
        return {
            "success": False,
            "status": "source_error",
            "error": str(error)
        }

    except Exception as error:
        return {
            "success": False,
            "status": "retrieval_error",
            "error": str(error)
        }
