
import re
from collections import OrderedDict


# ============================================================
# TEXT NORMALIZATION
# ============================================================

def normalize_text(text):
    """Normalize whitespace and common PDF text artifacts."""

    if not isinstance(text, str):
        return ""

    text = text.replace("\u00a0", " ")
    text = text.replace("\u2013", "-")
    text = text.replace("\u2014", "-")
    text = re.sub(r"[ \t]+", " ", text)
    text = re.sub(r"\s+", " ", text)

    return text.strip()


# ============================================================
# REFERENCE SECTION DETECTION
# ============================================================

REFERENCE_HEADINGS = [
    r"references",
    r"bibliography",
    r"works\s+cited",
    r"literature\s+cited",
    r"reference\s+list"
]


def find_reference_section(text):
    """
    Find the beginning of the reference section.

    Returns the reference section text.
    If no heading is found, returns an empty string.
    """

    if not isinstance(text, str) or not text.strip():
        return ""

    lines = text.splitlines()

    heading_pattern = re.compile(
        r"^\s*(?:" +
        "|".join(REFERENCE_HEADINGS) +
        r")\s*:?\s*$",
        re.IGNORECASE
    )

    for index, line in enumerate(lines):

        if heading_pattern.match(line.strip()):

            section = "\n".join(lines[index + 1:])

            # Stop at common document-ending sections.
            stop_pattern = re.compile(
                r"^\s*(?:appendix|acknowledg?ments|"
                r"author contributions|funding|"
                r"conflict of interest|data availability)\b",
                re.IGNORECASE
            )

            section_lines = []

            for section_line in section.splitlines():

                if stop_pattern.match(section_line.strip()):
                    break

                section_lines.append(section_line)

            return "\n".join(section_lines).strip()

    return ""


# ============================================================
# REFERENCE ENTRY DETECTION
# ============================================================

NUMBERED_REFERENCE_PATTERN = r"^\s*\[?(\d{1,4})\]?(?:[.)])?\s+"

AUTHOR_YEAR_PATTERN = re.compile(
    r"^\s*(?:[A-Z][A-Za-z'’-]+|[A-Z]\.)"
    r".{0,180}?\b(?:18|19|20)\d{2}[a-z]?\b"
)


def is_new_reference(line):
    """Determine whether a line starts a new reference."""

    line = normalize_text(line)

    if not line:
        return False

    if NUMBERED_REFERENCE_PATTERN.match(line):
        return True

    if AUTHOR_YEAR_PATTERN.match(line):
        return True

    return False


# ============================================================
# REFERENCE ENTRY EXTRACTION
# ============================================================

def extract_reference_entries(text):
    section = find_reference_section(text)

    if not section:
        return []

    lines = section.splitlines()

    references = []
    current_reference = None

    numbered_pattern = re.compile(
        r"^\s*\[?(\d{1,4})\]?(?:[.)])?\s+"
    )

    for line in lines:
        line = line.strip()

        if not line:
            continue

        match = numbered_pattern.match(line)

        if match:
            if current_reference:
                reference_text = " ".join(current_reference["parts"])

                references.append({
                    "number": current_reference["number"],
                    "reference_number": current_reference["number"],
                    "text": reference_text,
                    "reference_text": reference_text,
                    "style": "numeric"
                })

            current_reference = {
                "number": int(match.group(1)),
                "parts": [line[match.end():].strip()]
            }

        elif current_reference:
            current_reference["parts"].append(line)

    if current_reference:
        reference_text = " ".join(current_reference["parts"])

        references.append({
            "number": current_reference["number"],
            "reference_number": current_reference["number"],
            "text": reference_text,
            "reference_text": reference_text,
            "style": "numeric"
        })

    return references


# ============================================================
# CITATION EXTRACTION
# ============================================================

NUMERIC_CITATION_PATTERN = re.compile(
    r"\[(\d+(?:\s*[-–,;]\s*\d+)*)\]"
)

SUPERSCRIPT_LIKE_CITATION_PATTERN = re.compile(
    r"(?<!\w)(\d{1,3}(?:\s*[,;]\s*\d{1,3})+)(?!\w)"
)

AUTHOR_YEAR_CITATION_PATTERN = re.compile(
    r"\(([^()]{1,150}?"
    r"(?:18|19|20)\d{2}[a-z]?"
    r"(?:\s*;\s*[^()]{1,150}?"
    r"(?:18|19|20)\d{2}[a-z]?)*)\)"
)


def expand_numeric_citation(value):
    """
    Expand:
      1, 2, 3 -> [1, 2, 3]
      1-3 -> [1, 2, 3]
    """

    numbers = []

    parts = re.split(r"\s*[,;]\s*", str(value))

    for part in parts:

        range_match = re.match(
            r"^\s*(\d+)\s*[-–]\s*(\d+)\s*$",
            part
        )

        if range_match:

            start = int(range_match.group(1))
            end = int(range_match.group(2))

            if start <= end and end - start <= 100:
                numbers.extend(range(start, end + 1))

        else:

            number_match = re.match(r"^\s*(\d+)\s*$", part)

            if number_match:
                numbers.append(int(number_match.group(1)))

    return list(dict.fromkeys(numbers))


def extract_intext_citations(text):
    """
    Extract numeric and author-year citations.

    Returns individual citation dictionaries.

    Example:
      [1, 2, 3] -> three citation objects.
      (Smith, 2022) -> one author-year citation object.
    """

    if not isinstance(text, str) or not text.strip():
        return []

    citations = []

    # --------------------------------------------------------
    # NUMERIC CITATIONS
    # --------------------------------------------------------

    for match in NUMERIC_CITATION_PATTERN.finditer(text):

        numbers = expand_numeric_citation(match.group(1))

        for number in numbers:

            citations.append({
                "citation": f"[{number}]",
                "text": f"[{number}]",
                "value": str(number),
                "number": number,
                "style": "numeric",
                "start": match.start(),
                "end": match.end()
            })

    # --------------------------------------------------------
    # AUTHOR-YEAR CITATIONS
    # --------------------------------------------------------

    for match in AUTHOR_YEAR_CITATION_PATTERN.finditer(text):

        content = match.group(1)

        years = re.findall(
            r"\b((?:18|19|20)\d{2}[a-z]?)\b",
            content,
            re.IGNORECASE
        )

        if not years:
            continue

        for year in years:

            citations.append({
                "citation": f"({content.strip()})",
                "text": f"({content.strip()})",
                "value": content.strip(),
                "year": year,
                "style": "author_year",
                "start": match.start(),
                "end": match.end()
            })

    # --------------------------------------------------------
    # SORT AND REMOVE DUPLICATES
    # --------------------------------------------------------

    citations.sort(key=lambda item: item["start"])

    unique = []
    seen = set()

    for citation in citations:

        key = (
            citation["citation"].lower(),
            citation["start"],
            citation["style"]
        )

        if key not in seen:
            seen.add(key)
            unique.append(citation)

    return unique


# ============================================================
# AUTHOR AND YEAR EXTRACTION FROM REFERENCES
# ============================================================

def extract_reference_author(reference_text):
    """Extract a likely first-author surname."""

    text = normalize_text(reference_text)

    if not text:
        return ""

    # Common APA-like form: Smith, J. (2022).
    match = re.match(
        r"^([A-Z][A-Za-z'’-]+)\s*,",
        text
    )

    if match:
        return match.group(1).lower()

    # Common form: Smith J, Kumar R.
    match = re.match(
        r"^([A-Z][A-Za-z'’-]+)\s+[A-Z]\.?\s*[,;]",
        text
    )

    if match:
        return match.group(1).lower()

    # Common form: Smith et al. (2022).
    match = re.match(
        r"^([A-Z][A-Za-z'’-]+)\s+et\s+al",
        text,
        re.IGNORECASE
    )

    if match:
        return match.group(1).lower()

    return ""


def extract_reference_year(reference_text):
    """Extract the first likely publication year."""

    match = re.search(
        r"\b((?:18|19|20)\d{2})[a-z]?\b",
        reference_text
    )

    if match:
        return match.group(1)

    return ""


# ============================================================
# AUTHOR-YEAR MATCHING
# ============================================================

def match_author_year(citation_value, reference):
    """
    Compare author-year citation against a reference.

    This is a heuristic match. It should be manually reviewed
    when author formatting is ambiguous.
    """

    citation_text = normalize_text(citation_value).lower()

    reference_text = normalize_text(
        reference.get("reference_text", reference.get("text", ""))
    )

    citation_years = re.findall(
        r"\b((?:18|19|20)\d{2})[a-z]?\b",
        citation_text
    )

    reference_year = extract_reference_year(reference_text)

    if not citation_years or not reference_year:
        return False

    if reference_year not in citation_years:
        return False

    author = extract_reference_author(reference_text)

    if not author:
        return False

    # Check the reference's first-author surname in citation.
    citation_authors = re.findall(
        r"[A-Za-z'’-]+",
        citation_text
    )

    citation_authors = [
        item.lower()
        for item in citation_authors
    ]

    return author in citation_authors


# ============================================================
# CITATION TO REFERENCE MAPPING
# ============================================================

def map_citations_to_references(citations, references):
    """
    Map each extracted citation to its matching reference.

    Numeric:
      [1] -> reference number 1

    Author-year:
      (Smith, 2022) -> Smith's 2022 reference

    Returns one mapping object per citation.
    """

    if not isinstance(citations, list):
        return []

    if not isinstance(references, list):
        return []

    mappings = []

    for citation in citations:

        if isinstance(citation, dict):

            citation_text = (
                citation.get("citation")
                or citation.get("text")
                or citation.get("value")
                or ""
            )

            citation_style = citation.get("style", "")

        else:

            citation_text = str(citation)
            citation_style = ""

        citation_text = normalize_text(citation_text)

        if not citation_text:
            continue

        matched_references = []

        # ----------------------------------------------------
        # NUMERIC MAPPING
        # ----------------------------------------------------

        numeric_match = re.fullmatch(
            r"\[(\d+)\]",
            citation_text
        )

        if numeric_match or citation_style == "numeric":

            if numeric_match:
                citation_number = int(numeric_match.group(1))
            elif isinstance(citation, dict) and citation.get("number") is not None:
                citation_number = int(citation["number"])
            else:
                number_match = re.search(r"\d+", citation_text)
                citation_number = (
                    int(number_match.group())
                    if number_match else None
                )

            if citation_number is not None:

                for reference in references:

                    if not isinstance(reference, dict):
                        continue

                    reference_number = (
                        reference.get("number")
                        or reference.get("reference_number")
                    )

                    try:
                        reference_number = int(reference_number)
                    except (TypeError, ValueError):
                        continue

                    if reference_number == citation_number:
                        matched_references.append(reference)

        # ----------------------------------------------------
        # AUTHOR-YEAR MAPPING
        # ----------------------------------------------------

        elif citation_style == "author_year" or (
            citation_text.startswith("(")
            and re.search(r"(18|19|20)\d{2}", citation_text)
        ):

            for reference in references:

                if not isinstance(reference, dict):
                    continue

                if match_author_year(citation_text, reference):
                    matched_references.append(reference)

        # ----------------------------------------------------
        # BUILD RESULT
        # ----------------------------------------------------

        if matched_references:

            for reference in matched_references:

                mappings.append({
                    "citation": citation_text,
                    "reference_number": reference.get(
                        "number",
                        reference.get("reference_number")
                    ),
                    "mapping_status": "matched",
                    "reference": reference,
                    "reference_text": reference.get(
                        "reference_text",
                        reference.get("text", "")
                    )
                })

        else:

            mappings.append({
                "citation": citation_text,
                "reference_number": None,
                "mapping_status": "unmatched",
                "reference": None,
                "reference_text": None
            })

    return mappings


# ============================================================
# CLAIM-TO-CITATION POSITION MAPPING
# ============================================================

def map_claims_to_citations(claims, citations, window=500):
    """
    Associate citations with claims using their positions
    in the original document text.

    Claims must contain start/end character positions.

    This function is optional unless your claim extractor
    supplies positions.
    """

    results = []

    for claim in claims:

        claim_start = claim.get("start")
        claim_end = claim.get("end")

        linked_citations = []

        if claim_start is None or claim_end is None:
            results.append({
                "claim": claim,
                "citations": [],
                "mapping_status": "position_unavailable"
            })
            continue

        for citation in citations:

            citation_start = citation.get("start")

            if citation_start is None:
                continue

            if (
                claim_start <= citation_start <= claim_end + window
            ):
                linked_citations.append(citation)

        results.append({
            "claim": claim,
            "citations": linked_citations,
            "mapping_status": (
                "linked" if linked_citations else "no_citation_found"
            )
        })

    return results


# ============================================================
# COMPLETE CLAIM-TO-REFERENCE MAPPING
# ============================================================

def map_claims_to_references(claims, references):
    """
    Map citations found inside each claim to references.

    This function supports claim dictionaries containing
    claim text under 'claim' or 'text'.
    """

    results = []

    for index, claim in enumerate(claims):

        if isinstance(claim, dict):

            claim_text = (
                claim.get("claim")
                or claim.get("text")
                or ""
            )

            claim_id = claim.get("id", index + 1)

        else:

            claim_text = str(claim)
            claim_id = index + 1

        citations = extract_intext_citations(claim_text)

        linked_references = map_citations_to_references(
            citations,
            references
        )

        matched = [
            item for item in linked_references
            if item.get("mapping_status") == "matched"
        ]

        results.append({
            "claim_id": claim_id,
            "claim": claim_text,
            "citations": citations,
            "linked_references": linked_references,
            "linked_reference_count": len(matched),
            "link_status": (
                "linked" if matched else "no_matching_reference"
            )
        })

    return results
