
import requests
import re
from difflib import SequenceMatcher


CROSSREF_URL = "https://api.crossref.org/works"


def normalize_text(text):
    text = re.sub(r"[^a-zA-Z0-9 ]", " ", text.lower())
    return re.sub(r"\s+", " ", text).strip()


def similarity_score(first, second):
    return round(
        SequenceMatcher(
            None,
            normalize_text(first),
            normalize_text(second)
        ).ratio(),
        3
    )


def retrieve_research(reference_text):
    """
    Search Crossref for a real publication matching
    the extracted bibliography entry.
    """

    try:

        response = requests.get(
            CROSSREF_URL,
            params={
                "query.bibliographic": reference_text,
                "rows": 3
            },
            headers={
                "User-Agent": "CiteVerifyAI/1.0 (Academic Research Verification)"
            },
            timeout=15
        )

        response.raise_for_status()

        data = response.json()

        items = data.get("message", {}).get("items", [])

        results = []

        for item in items:

            titles = item.get("title", [])

            title = titles[0] if titles else "Title unavailable"

            authors = []

            for author in item.get("author", []):

                name = " ".join([
                    author.get("given", ""),
                    author.get("family", "")
                ]).strip()

                if name:
                    authors.append(name)

            published = (
                item.get("published-print")
                or item.get("published-online")
                or item.get("created")
            )

            year = None

            if published:

                date_parts = published.get(
                    "date-parts", [[None]]
                )

                if date_parts and date_parts[0]:
                    year = date_parts[0][0]

            score = similarity_score(
                reference_text,
                title
            )

            results.append({

                "title": title,

                "authors": authors,

                "year": year,

                "doi": item.get("DOI"),

                "url": item.get("URL"),

                "publisher": item.get("publisher"),

                "journal": (
                    item.get("container-title", [None])[0]
                    if item.get("container-title")
                    else None
                ),

                "similarity": score

            })

        results.sort(
            key=lambda result: result["similarity"],
            reverse=True
        )

        best_match = results[0] if results else None

        # Metadata matching is not evidence verification.
        if best_match and best_match["similarity"] >= 0.65:
            status = "candidate_found"
        else:
            status = "needs_review"

        return {
            "success": True,
            "status": status,
            "best_match": best_match,
            "candidates": results
        }

    except requests.exceptions.Timeout:

        return {
            "success": False,
            "status": "timeout",
            "error": "Crossref request timed out"
        }

    except requests.exceptions.RequestException as error:

        return {
            "success": False,
            "status": "api_error",
            "error": str(error)
        }

    except Exception as error:

        return {
            "success": False,
            "status": "error",
            "error": str(error)
        }
