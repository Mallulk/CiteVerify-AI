
import re
import fitz
import traceback

from io import BytesIO
from datetime import datetime
from xml.sax.saxutils import escape

from flask import Flask, jsonify, request, send_file
from flask_cors import CORS

from reportlab.lib import colors
from reportlab.lib.enums import TA_CENTER
from reportlab.lib.pagesizes import A4
from reportlab.lib.styles import getSampleStyleSheet, ParagraphStyle
from reportlab.lib.units import mm
from reportlab.platypus import (
    SimpleDocTemplate,
    Paragraph,
    Spacer,
    Table,
    TableStyle,
    KeepTogether
)

from services.reference_extractor import (
    find_reference_section,
    extract_reference_entries,
    extract_intext_citations,
    map_citations_to_references
)

from services.crossref_service import retrieve_research
from services.evidence_service import retrieve_evidence
from services.verification_service import (
    verify_claim_against_passages
)


# ==================================================
# APPLICATION CONFIGURATION
# ==================================================

app = Flask(__name__)
CORS(app)

app.config["MAX_CONTENT_LENGTH"] = 15 * 1024 * 1024


# ==================================================
# PDF TEXT EXTRACTION
# ==================================================

def extract_pdf(file_bytes):

    document = fitz.open(
        stream=file_bytes,
        filetype="pdf"
    )

    pages = []
    full_text = ""

    try:
        for page_number, page in enumerate(document, start=1):

            page_text = page.get_text("text")

            pages.append({
                "page": page_number,
                "text": page_text
            })

            full_text += "\n" + page_text

    finally:
        document.close()

    return full_text, pages


# ==================================================
# REFERENCE NORMALIZATION
# ==================================================

def normalize_reference_entries(raw_references):

    normalized_references = []

    if not isinstance(raw_references, (list, tuple)):
        return normalized_references

    for index, reference in enumerate(raw_references, start=1):

        if isinstance(reference, str):

            reference_text = reference.strip()
            reference_number = index
            style = "unknown"
            original_data = {}

        elif isinstance(reference, dict):

            reference_text = (
                reference.get("text")
                or reference.get("reference_text")
                or reference.get("reference")
                or reference.get("raw")
                or reference.get("entry")
                or ""
            )

            reference_text = str(reference_text).strip()

            reference_number = (
                reference.get("number")
                or reference.get("reference_number")
                or index
            )

            style = reference.get("style", "unknown")
            original_data = reference.copy()

        else:
            continue

        if not reference_text:
            continue

        normalized_references.append({
            **original_data,
            "number": reference_number,
            "reference_number": reference_number,
            "text": reference_text,
            "reference_text": reference_text,
            "style": style
        })

    return normalized_references


# ==================================================
# CLAIM EXTRACTION
# ==================================================

def extract_claims(text):

    text = re.sub(r"\s+", " ", text).strip()

    sentences = re.split(
        r'(?<=[.!?])\s+(?=[A-Z0-9("\[])',
        text
    )

    claim_patterns = [

        r"\bresearch shows\b",
        r"\bstudy found\b",
        r"\bstudies show\b",
        r"\bresults indicate\b",
        r"\bresults demonstrate\b",
        r"\bevidence suggests\b",
        r"\bfindings reveal\b",
        r"\bwe found\b",

        r"\bdemonstrates?\b",
        r"\bsuggests?\b",
        r"\breveals?\b",
        r"\bindicates?\b",
        r"\bconcludes?\b",
        r"\bconfirms?\b",

        r"\bincreased\b",
        r"\bdecreased\b",
        r"\bimproved\b",
        r"\breduced\b",
        r"\bhigher than\b",
        r"\blower than\b",
        r"\bgreater than\b",
        r"\bless than\b",
        r"\boutperformed\b",
        r"\bsuperior to\b",

        r"\b\d+(?:\.\d+)?\s*%",
        r"\b\d+(?:\.\d+)?\s*(?:times|fold)\b",
        r"\bcorrelation\b",
        r"\bstatistically significant\b",
        r"\bsignificant difference\b",
        r"\bp\s*[<=>]\s*0?\.\d+",

        r"\bleads to\b",
        r"\bresults in\b",
        r"\bdue to\b",
        r"\bcauses?\b",
        r"\bassociated with\b",
        r"\bcorrelated with\b",
        r"\bcontributes to\b",

        r"\baccording to\b",
        r"\bthe data show\b",
        r"\bthe analysis shows\b",
        r"\bthe model achieved\b",
        r"\bthe proposed method\b"

    ]

    claims = []
    seen = set()

    for sentence in sentences:

        sentence = sentence.strip()

        if len(sentence) < 35 or len(sentence) > 700:
            continue

        if re.match(
            r"^(references|bibliography|appendix|figure|table)\b",
            sentence,
            re.IGNORECASE
        ):
            continue

        normalized = re.sub(
            r"\s+",
            " ",
            sentence
        ).strip()

        lower = normalized.lower()

        matched = any(
            re.search(pattern, lower)
            for pattern in claim_patterns
        )

        if matched and normalized not in seen:

            claims.append({
                "id": len(claims) + 1,
                "claim": normalized,
                "type": "Potential research claim",
                "detection_reason": "Research statement pattern detected"
            })

            seen.add(normalized)

        if len(claims) >= 30:
            break

    return claims


# ==================================================
# UPLOADED DOCUMENT EVIDENCE RETRIEVAL
# ==================================================

def find_document_passages(claim, pages, max_results=3):

    stop_words = {
        "the", "and", "for", "with", "from", "that",
        "this", "were", "was", "are", "is", "of",
        "in", "on", "to", "a", "an", "by", "as",
        "at", "it", "their", "they", "which", "these",
        "those", "following", "after", "before"
    }

    def get_terms(value):

        words = re.findall(r"[a-z0-9]+", value.lower())

        return {
            word for word in words
            if word not in stop_words
            and (len(word) > 2 or word.isdigit())
        }

    claim_terms = get_terms(claim)

    if not claim_terms:
        return []

    claim_normalized = re.sub(
        r"\s+", " ", claim.lower()
    ).strip()

    candidates = []

    for page_data in pages:

        page_number = page_data.get("page")
        page_text = page_data.get("text", "")

        if not page_text.strip():
            continue

        clean_page_text = re.sub(
            r"\s+", " ", page_text
        ).strip()

        sentences = re.split(
            r'(?<=[.!?])\s+(?=[A-Z0-9("\[])',
            clean_page_text
        )

        for sentence in sentences:

            sentence = sentence.strip()

            if len(sentence) < 30:
                continue

            passage_terms = get_terms(sentence)

            if not passage_terms:
                continue

            overlap = len(
                claim_terms.intersection(passage_terms)
            ) / len(claim_terms)

            passage_normalized = sentence.lower()

            if (
                claim_normalized in passage_normalized
                or passage_normalized in claim_normalized
            ):
                overlap = 1.0

            if overlap >= 0.15:

                candidates.append({
                    "page": page_number,
                    "passage": sentence,
                    "relevance_score": round(overlap, 4),
                    "source_type": "uploaded_document"
                })

    candidates.sort(
        key=lambda item: item["relevance_score"],
        reverse=True
    )

    unique_candidates = []
    seen = set()

    for item in candidates:

        key = re.sub(
            r"\s+", " ", item["passage"].lower()
        ).strip()

        if key in seen:
            continue

        seen.add(key)
        unique_candidates.append(item)

        if len(unique_candidates) >= max_results:
            break

    return unique_candidates


# ==================================================
# LEGACY CITATION EXTRACTION
# ==================================================

def extract_citations(text):

    patterns = [

        r'\[\d+(?:\s*[-,;]\s*\d+)*\]',

        r'\([A-Z][A-Za-z\-]+(?:\s+et\s+al\.)?,\s*(?:19|20)\d{2}\)'

    ]

    citations = set()

    for pattern in patterns:

        matches = re.findall(pattern, text)

        for match in matches:
            citations.add(match)

    return sorted(citations)


# ==================================================
# CLAIM-TO-CITATION LINKING
# ==================================================

def link_claims_to_citations(claims, references, pages=None):

    claim_citation_links = []

    for claim in claims:

        claim_text = claim.get("claim", "")

        claim_citations = extract_intext_citations(
            claim_text
        )

        linked_references = map_citations_to_references(
            claim_citations,
            references
        )

        matched_references = [
            item for item in linked_references
            if item.get("mapping_status") == "matched"
        ]

        document_passages = find_document_passages(
            claim_text,
            pages or [],
            max_results=3
        )

        claim_citation_links.append({

            "claim_id": claim.get("id"),
            "claim": claim_text,
            "citations": claim_citations,
            "linked_references": linked_references,
            "linked_reference_count": len(matched_references),

            "link_status": (
                "linked"
                if matched_references
                else "no_matching_reference"
            ),

            "document_passages": document_passages

        })

    return claim_citation_links


# ==================================================
# HEALTH CHECK
# ==================================================

@app.route("/", methods=["GET"])
def home():

    return jsonify({
        "project": "CiteVerify AI",
        "description": "Research Trust Intelligence Platform",
        "status": "running",
        "version": "1.2.0"
    })


@app.route("/api/health", methods=["GET"])
def health():

    return jsonify({
        "success": True,
        "service": "CiteVerify AI Backend",
        "status": "healthy"
    })


# ==================================================
# DOCUMENT ANALYZER API
# ==================================================

@app.route("/api/analyze", methods=["POST"])
def analyze_document():

    try:

        if "file" not in request.files:
            return jsonify({
                "success": False,
                "error": "No PDF file uploaded"
            }), 400

        file = request.files["file"]

        if not file.filename:
            return jsonify({
                "success": False,
                "error": "Please select a file"
            }), 400

        if not file.filename.lower().endswith(".pdf"):
            return jsonify({
                "success": False,
                "error": "Only PDF files are supported"
            }), 400

        file_bytes = file.read()

        if not file_bytes:
            return jsonify({
                "success": False,
                "error": "The uploaded file is empty"
            }), 400

        text, pages = extract_pdf(file_bytes)

        if not text.strip():
            return jsonify({
                "success": False,
                "error": "No readable text found. Scanned PDFs require OCR."
            }), 422

        claims = extract_claims(text)

        citations = extract_citations(text)

        raw_references = extract_reference_entries(text)

        references = normalize_reference_entries(
            raw_references
        )

        reference_section = find_reference_section(text)

        print("\n========== REFERENCE DEBUG ==========")

        print("PDF TEXT LENGTH:", len(text))

        print(
            "REFERENCE SECTION FOUND:",
            bool(reference_section)
        )

        print(
            "RAW REFERENCE COUNT:",
            len(raw_references)
            if isinstance(raw_references, (list, tuple))
            else "Invalid format"
        )

        print("NORMALIZED REFERENCE COUNT:", len(references))

        for reference in references:
            print(
                reference["number"],
                "->",
                reference["text"]
            )

        print("=====================================\n")

        intext_citations = extract_intext_citations(text)

        citation_mapping = map_citations_to_references(
            intext_citations,
            references
        )

        mapped_count = sum(
            1 for item in citation_mapping
            if item.get("mapping_status") == "matched"
        )

        unmatched_count = sum(
            1 for item in citation_mapping
            if item.get("mapping_status") == "unmatched"
        )

        claim_citation_links = link_claims_to_citations(
            claims,
            references,
            pages
        )

        linked_claim_count = sum(
            1 for item in claim_citation_links
            if item["link_status"] == "linked"
        )

        unlinked_claim_count = (
            len(claim_citation_links) - linked_claim_count
        )

        print("\n========== CLAIM-CITATION LINKING ==========")

        for item in claim_citation_links:

            print("\nClaim ID:", item["claim_id"])
            print("Citations:", item["citations"])

            print(
                "Linked references:",
                item["linked_reference_count"]
            )

            print("Status:", item["link_status"])

        print("\nTOTAL CLAIMS:", len(claim_citation_links))
        print("LINKED CLAIMS:", linked_claim_count)
        print("UNLINKED CLAIMS:", unlinked_claim_count)

        print("============================================\n")

        word_count = len(text.split())

        response_data = {

            "success": True,

            "document": {
                "name": file.filename,
                "pages": len(pages),
                "characters": len(text),
                "word_count": word_count
            },

            "analysis": {
                "total_claims": len(claims),
                "total_citations": len(citations),
                "total_references": len(references),
                "total_intext_citations": len(intext_citations),
                "mapped_citations": mapped_count,
                "unmatched_citations": unmatched_count,
                "linked_claims": linked_claim_count,
                "unlinked_claims": unlinked_claim_count
            },

            "claims": claims,
            "citations": citations,
            "references": references,
            "reference_count": len(references),
            "intext_citations": citation_mapping,
            "claim_citation_links": claim_citation_links,
            "preview": text[:5000],

            "message": "Document analysis completed successfully"

        }

        print("\n========== FINAL API DEBUG ==========")

        print(
            "FINAL API REFERENCE COUNT:",
            response_data["reference_count"]
        )

        print(
            "FINAL API CLAIM COUNT:",
            response_data["analysis"]["total_claims"]
        )

        print(
            "FINAL API LINKED CLAIMS:",
            response_data["analysis"]["linked_claims"]
        )

        print("API RESPONSE READY")
        print("=====================================\n")

        return jsonify(response_data), 200

    except Exception as error:

        print("\n========== DOCUMENT ANALYSIS ERROR ==========")

        print("ERROR:", str(error))

        traceback.print_exc()

        print("==============================================\n")

        return jsonify({
            "success": False,
            "error": str(error)
        }), 500


# ==================================================
# CROSSREF RESEARCH RETRIEVAL API
# ==================================================

@app.route("/api/research/retrieve", methods=["POST"])
def retrieve_references():

    try:

        data = request.get_json(silent=True) or {}

        references = data.get("references", [])

        if not isinstance(references, list):
            return jsonify({
                "success": False,
                "error": "References must be a list"
            }), 400

        if not references:
            return jsonify({
                "success": False,
                "error": "No references provided"
            }), 400

        if len(references) > 20:
            return jsonify({
                "success": False,
                "error": "Maximum 20 references per request"
            }), 400

        results = []

        for index, reference in enumerate(references, start=1):

            if isinstance(reference, dict):

                reference_text = (
                    reference.get("text")
                    or reference.get("reference_text")
                    or reference.get("reference")
                    or ""
                )

                reference_number = (
                    reference.get("number")
                    or reference.get("reference_number")
                    or index
                )

            elif isinstance(reference, str):

                reference_text = reference
                reference_number = index

            else:
                continue

            reference_text = str(reference_text).strip()

            if not reference_text:
                continue

            research = retrieve_research(reference_text)

            results.append({
                "reference_number": reference_number,
                "reference_text": reference_text,
                "research": research
            })

        matched = sum(
            1 for item in results
            if isinstance(item.get("research"), dict)
            and item["research"].get("status") == "candidate_found"
        )

        return jsonify({

            "success": True,
            "total_references": len(results),
            "candidate_matches": matched,
            "needs_review": len(results) - matched,
            "results": results

        }), 200

    except Exception as error:

        print("\nRESEARCH RETRIEVAL ERROR:", str(error))

        traceback.print_exc()

        return jsonify({
            "success": False,
            "error": str(error)
        }), 500


# ==================================================
# RESEARCH EVIDENCE RETRIEVAL API
# ==================================================

@app.route("/api/evidence/retrieve", methods=["POST"])
def evidence_retrieval():

    try:

        data = request.get_json(silent=True) or {}

        claim = data.get("claim", "")
        publication = data.get("publication", {})

        if not isinstance(claim, str) or not claim.strip():
            return jsonify({
                "success": False,
                "error": "A research claim is required"
            }), 400

        if not isinstance(publication, dict):
            return jsonify({
                "success": False,
                "error": "Publication must be an object"
            }), 400

        result = retrieve_evidence(
            claim.strip(),
            publication
        )

        return jsonify({
            "success": True,
            "claim": claim.strip(),
            "evidence": result
        }), 200

    except Exception as error:

        print("EVIDENCE RETRIEVAL ERROR:", str(error))

        traceback.print_exc()

        return jsonify({
            "success": False,
            "error": str(error)
        }), 500


# ==================================================
# PDF VERIFICATION REPORT GENERATOR
# ==================================================

@app.route("/api/report/pdf", methods=["POST"])
def generate_pdf_report():

    try:

        data = request.get_json(silent=True) or {}

        document = data.get("document") or {}
        analysis = data.get("analysis") or {}
        citation_summary = data.get("citation_summary") or {}
        results = data.get("results") or []

        if not isinstance(document, dict):
            return jsonify({
                "success": False,
                "error": "Invalid document information."
            }), 400

        if not isinstance(analysis, dict):
            return jsonify({
                "success": False,
                "error": "Invalid analysis information."
            }), 400

        if not isinstance(citation_summary, dict):
            return jsonify({
                "success": False,
                "error": "Invalid citation summary."
            }), 400

        if not isinstance(results, list):
            return jsonify({
                "success": False,
                "error": "Invalid report results."
            }), 400

        buffer = BytesIO()

        pdf = SimpleDocTemplate(
            buffer,
            pagesize=A4,
            rightMargin=18 * mm,
            leftMargin=18 * mm,
            topMargin=18 * mm,
            bottomMargin=18 * mm,
            title="CiteVerify AI Verification Report",
            author="CiteVerify AI"
        )

        styles = getSampleStyleSheet()

        styles.add(ParagraphStyle(
            name="ReportTitle",
            parent=styles["Title"],
            textColor=colors.HexColor("#14213D"),
            fontSize=22,
            leading=27,
            alignment=TA_CENTER,
            spaceAfter=12
        ))

        styles.add(ParagraphStyle(
            name="SectionHeading",
            parent=styles["Heading2"],
            textColor=colors.HexColor("#B68A35"),
            fontSize=13,
            spaceBefore=16,
            spaceAfter=8
        ))

        styles.add(ParagraphStyle(
            name="ReportSmall",
            parent=styles["BodyText"],
            fontSize=8,
            leading=11,
            textColor=colors.HexColor("#555555")
        ))

        styles.add(ParagraphStyle(
            name="ReportEvidence",
            parent=styles["BodyText"],
            fontSize=9,
            leading=13,
            leftIndent=8,
            borderColor=colors.HexColor("#D8DCE5"),
            borderWidth=0.5,
            borderPadding=6,
            spaceAfter=7
        ))

        story = []

        def add_paragraph(value, style="BodyText"):

            safe_text = escape(
                str(value if value is not None else "")
            )

            story.append(
                Paragraph(safe_text, styles[style])
            )

        def add_section(title):

            story.append(
                Paragraph(
                    escape(title),
                    styles["SectionHeading"]
                )
            )

        def add_table(rows, widths):

            table = Table(
                rows,
                colWidths=widths,
                repeatRows=1
            )

            table.setStyle(TableStyle([

                ("BACKGROUND", (0, 0), (-1, 0),
                 colors.HexColor("#14213D")),

                ("TEXTCOLOR", (0, 0), (-1, 0),
                 colors.white),

                ("FONTNAME", (0, 0), (-1, 0),
                 "Helvetica-Bold"),

                ("FONTSIZE", (0, 0), (-1, -1), 8),

                ("GRID", (0, 0), (-1, -1), 0.4,
                 colors.HexColor("#D8DCE5")),

                ("VALIGN", (0, 0), (-1, -1), "TOP"),

                ("LEFTPADDING", (0, 0), (-1, -1), 7),

                ("RIGHTPADDING", (0, 0), (-1, -1), 7),

                ("TOPPADDING", (0, 0), (-1, -1), 7),

                ("BOTTOMPADDING", (0, 0), (-1, -1), 7),

                ("ROWBACKGROUNDS", (0, 1), (-1, -1), [
                    colors.white,
                    colors.HexColor("#F5F6F9")
                ])

            ]))

            story.append(table)
            story.append(Spacer(1, 8))

        # ------------------------------------------
        # REPORT TITLE
        # ------------------------------------------

        story.append(
            Paragraph(
                "CiteVerify AI",
                styles["ReportTitle"]
            )
        )

        add_paragraph(
            "Research Trust & Evidence Intelligence Report",
            "Heading2"
        )

        add_paragraph(
            "Generated on: " + datetime.now().strftime(
                "%d %B %Y, %I:%M %p"
            ),
            "ReportSmall"
        )

        story.append(Spacer(1, 12))

        # ------------------------------------------
        # DOCUMENT INFORMATION
        # ------------------------------------------

        add_section("1. Document Information")

        document_rows = [
            ["Field", "Value"],
            [
                "Document",
                str(document.get("name", "Not provided"))
            ],
            [
                "Pages",
                str(document.get("pages", "N/A"))
            ],
            [
                "Word Count",
                str(document.get("word_count", "N/A"))
            ],
            [
                "Total Claims",
                str(analysis.get("total_claims", len(results)))
            ],
            [
                "Total References",
                str(
                    analysis.get(
                        "total_references",
                        citation_summary.get("references", "N/A")
                    )
                )
            ]
        ]

        add_table(
            document_rows,
            [55 * mm, 115 * mm]
        )

        # ------------------------------------------
        # CITATION INTEGRITY
        # ------------------------------------------

        add_section("2. Citation Integrity")

        citation_rows = [
            ["Metric", "Count"],
            [
                "Total In-text Citations",
                str(
                    citation_summary.get(
                        "total",
                        analysis.get("total_intext_citations", 0)
                    )
                )
            ],
            [
                "Matched Citations",
                str(
                    citation_summary.get(
                        "matched",
                        analysis.get("mapped_citations", 0)
                    )
                )
            ],
            [
                "Unmatched Citations",
                str(
                    citation_summary.get(
                        "unmatched",
                        analysis.get("unmatched_citations", 0)
                    )
                )
            ],
            [
                "References",
                str(
                    citation_summary.get(
                        "references",
                        analysis.get("total_references", 0)
                    )
                )
            ]
        ]

        add_table(
            citation_rows,
            [85 * mm, 85 * mm]
        )

        # ------------------------------------------
        # VERIFICATION SUMMARY
        # ------------------------------------------

        add_section("3. AI Verification Summary")

        status_counts = {
            "Supported": 0,
            "Contradicted": 0,
            "Insufficient Evidence": 0,
            "Manual Review": 0
        }

        for claim in results:

            if not isinstance(claim, dict):
                continue

            sources = claim.get("evidence_results", [])

            if not isinstance(sources, list):
                continue

            claim_statuses = []

            for source in sources:

                if not isinstance(source, dict):
                    continue

                # Use the actual status from verification_service.py
                status = source.get("verification_status")

                if not status:

                    verification = source.get("verification") or {}

                    if isinstance(verification, dict):
                        status = verification.get("status", "")

                if status:
                    claim_statuses.append(str(status).lower())

            if "contradicted" in claim_statuses:

                status_counts["Contradicted"] += 1

            elif "supported" in claim_statuses:

                status_counts["Supported"] += 1

            elif "insufficient_evidence" in claim_statuses:

                status_counts["Insufficient Evidence"] += 1

            else:

                status_counts["Manual Review"] += 1

        summary_rows = [
            ["Verification Status", "Number of Claims"]
        ]

        for status, count in status_counts.items():

            summary_rows.append([
                status,
                str(count)
            ])

        add_table(
            summary_rows,
            [100 * mm, 70 * mm]
        )

        # ------------------------------------------
        # DETAILED CLAIM VERIFICATION
        # ------------------------------------------

        add_section("4. Detailed Claim Verification")

        if not results:

            add_paragraph(
                "No claim verification results were supplied."
            )

        for index, claim in enumerate(results, start=1):

            if not isinstance(claim, dict):
                continue

            claim_text = claim.get(
                "claim",
                "Claim text unavailable"
            )

            story.append(Spacer(1, 10))

            add_paragraph(
                f"Claim {index}",
                "Heading3"
            )

            add_paragraph(
                claim_text
            )

            sources = claim.get("evidence_results", [])

            if not isinstance(sources, list) or not sources:

                add_paragraph(
                    "No evidence sources available.",
                    "ReportSmall"
                )

                continue

            for source_index, source in enumerate(sources, start=1):

                if not isinstance(source, dict):
                    continue

                publication = source.get("publication") or {}

                if not isinstance(publication, dict):
                    publication = {}

                publication_title = (
                    publication.get("title")
                    or source.get("reference_text")
                    or "Unknown publication"
                )

                reference_number = source.get(
                    "reference_number",
                    "Uploaded document"
                )

                add_paragraph(
                    f"Source {source_index}: {publication_title}",
                    "Heading4"
                )

                add_paragraph(
                    f"Reference: {reference_number}",
                    "ReportSmall"
                )

                verification = source.get("verification") or {}

                if not isinstance(verification, dict):
                    verification = {}

                status = (
                    source.get("verification_status")
                    or verification.get("status")
                    or "needs_manual_review"
                )

                add_paragraph(
                    f"Overall Status: {str(status).replace('_', ' ').title()}"
                )

                assessments = verification.get(
                    "assessments",
                    []
                )

                if not isinstance(assessments, list):
                    assessments = []

                if not assessments:

                    add_paragraph(
                        verification.get("message")
                        or source.get("message")
                        or "No passage-level assessment available.",
                        "ReportSmall"
                    )

                for passage_index, item in enumerate(
                    assessments,
                    start=1
                ):

                    if not isinstance(item, dict):
                        continue

                    assessment = item.get("assessment") or {}

                    if not isinstance(assessment, dict):
                        assessment = {}

                    add_paragraph(
                        f"Evidence Passage {passage_index}",
                        "Heading5"
                    )

                    add_paragraph(
                        f"Page: {item.get('page', 'N/A')}",
                        "ReportSmall"
                    )

                    add_paragraph(
                        item.get(
                            "passage",
                            "Evidence passage unavailable"
                        ),
                        "ReportEvidence"
                    )

                    passage_status = assessment.get(
                        "status",
                        "N/A"
                    )

                    confidence = assessment.get(
                        "confidence",
                        "N/A"
                    )

                    add_paragraph(
                        f"Assessment: {str(passage_status).replace('_', ' ').title()}",
                        "ReportSmall"
                    )

                    add_paragraph(
                        f"Confidence: {confidence}",
                        "ReportSmall"
                    )

                    scores = assessment.get("scores")

                    if isinstance(scores, dict) and scores:

                        score_text = " | ".join(
                            f"{key}: {value}"
                            for key, value in scores.items()
                        )

                        add_paragraph(
                            "NLI Scores: " + score_text,
                            "ReportSmall"
                        )

                story.append(Spacer(1, 8))

        # ------------------------------------------
        # LIMITATIONS
        # ------------------------------------------

        add_section("5. Important Limitations")

        limitations = [

            "AI verification is an automated assessment and is not a substitute for expert scientific review.",

            "Supported means the retrieved passage is predicted to support the claim; it does not independently establish scientific truth.",

            "Contradicted indicates a possible conflict between the claim and the retrieved passage.",

            "Insufficient evidence means the available passages do not provide enough information for a reliable assessment.",

            "Publication metadata matching does not prove that a publication supports a research claim.",

            "Results should be reviewed by a qualified human before being used as scientific conclusions."

        ]

        for limitation in limitations:

            add_paragraph(
                "• " + limitation,
                "ReportSmall"
            )

            story.append(Spacer(1, 4))

        # ------------------------------------------
        # REPORT FOOTER
        # ------------------------------------------

        story.append(Spacer(1, 20))

        add_paragraph(
            "Generated by CiteVerify AI – Research Trust & Evidence Intelligence Platform",
            "ReportSmall"
        )

        pdf.build(story)

        buffer.seek(0)
        print("PDF GENERATED SIZE:", len(buffer.getvalue()))

        return send_file(
            buffer,
            mimetype="application/pdf",
            as_attachment=True,
            download_name="CiteVerify_AI_Verification_Report.pdf"
        )

    except Exception as error:

        print("\nPDF REPORT GENERATION ERROR:", str(error))

        traceback.print_exc()

        return jsonify({
            "success": False,
            "error": str(error)
        }), 500


# ==================================================
# AI CLAIM VERIFICATION API
# ==================================================

@app.route("/api/evidence/verify", methods=["POST"])
def verify_research_claim():

    try:

        data = request.get_json(silent=True) or {}

        claim = data.get("claim", "")
        passages = data.get("passages", [])

        if not isinstance(claim, str) or not claim.strip():
            return jsonify({
                "success": False,
                "error": "A research claim is required"
            }), 400

        if not isinstance(passages, list):
            return jsonify({
                "success": False,
                "error": "Passages must be a list"
            }), 400

        if len(passages) > 20:
            return jsonify({
                "success": False,
                "error": "Maximum 20 passages per request"
            }), 400

        result = verify_claim_against_passages(
            claim.strip(),
            passages
        )

        return jsonify({
            "success": True,
            "claim": claim.strip(),
            "verification": result
        }), 200

    except Exception as error:

        print("AI VERIFICATION ERROR:", str(error))

        traceback.print_exc()

        return jsonify({
            "success": False,
            "error": str(error)
        }), 500


# ==================================================
# AUTOMATIC CLAIM-TO-EVIDENCE + AI VERIFICATION
# ==================================================

@app.route("/api/evidence/analyze", methods=["POST"])
def analyze_claim_evidence():

    try:

        data = request.get_json(silent=True) or {}

        claim_links = data.get("claim_citation_links", [])
        references = data.get("references", [])

        if not isinstance(claim_links, list):
            return jsonify({
                "success": False,
                "error": "claim_citation_links must be a list"
            }), 400

        if not isinstance(references, list):
            return jsonify({
                "success": False,
                "error": "references must be a list"
            }), 400

        if not claim_links:
            return jsonify({
                "success": False,
                "error": "No claim-citation links provided"
            }), 400

        reference_lookup = {}

        for index, reference in enumerate(references, start=1):

            if not isinstance(reference, dict):
                continue

            number = reference.get(
                "number",
                reference.get("reference_number", index)
            )

            reference_lookup[str(number)] = reference

        results = []

        for claim_item in claim_links:

            if not isinstance(claim_item, dict):
                continue

            claim_text = claim_item.get("claim", "")

            if not isinstance(claim_text, str) or not claim_text.strip():
                continue

            claim_text = claim_text.strip()

            linked_references = claim_item.get(
                "linked_references",
                []
            )

            claim_result = {
                "claim_id": claim_item.get("claim_id"),
                "claim": claim_text,
                "evidence_results": []
            }

            # ------------------------------------------
            # VERIFY AGAINST UPLOADED PDF
            # ------------------------------------------

            document_passages = claim_item.get(
                "document_passages",
                []
            )

            claim_result["document_evidence_found"] = bool(
                document_passages
            )

            if document_passages:

                document_verification = verify_claim_against_passages(
                    claim_text,
                    document_passages
                )

                document_status = (
                    document_verification.get(
                        "status",
                        "needs_manual_review"
                    )
                    if isinstance(document_verification, dict)
                    else "needs_manual_review"
                )

                claim_result["evidence_results"].append({

                    "source_type": "uploaded_document",

                    "reference_number": None,

                    "reference_text": "Uploaded research PDF",

                    "publication": {
                        "title": "Uploaded Document",
                        "source_type": "uploaded_document"
                    },

                    "evidence": {
                        "success": True,
                        "status": "document_passages_found",
                        "passages": document_passages
                    },

                    "verification": document_verification,

                    "verification_status": document_status

                })

            if not isinstance(linked_references, list):
                linked_references = []

            # ------------------------------------------
            # PROCESS LINKED REFERENCES
            # ------------------------------------------

            for linked in linked_references:

                if not isinstance(linked, dict):
                    continue

                if linked.get("mapping_status") != "matched":
                    continue

                reference_number = (
                    linked.get("reference_number")
                    or linked.get("number")
                )

                reference = reference_lookup.get(
                    str(reference_number)
                )

                if not reference:
                    reference = linked

                reference_text = (

                    reference.get("text")
                    or reference.get("reference_text")
                    or reference.get("reference")
                    or linked.get("text")
                    or linked.get("reference_text")
                    or ""

                )

                if not reference_text:
                    continue

                # Retrieve publication metadata

                research = retrieve_research(reference_text)

                best_match = (
                    research.get("best_match")
                    if isinstance(research, dict)
                    else None
                )

                if not isinstance(best_match, dict):

                    claim_result["evidence_results"].append({

                        "reference_number": reference_number,

                        "reference_text": reference_text,

                        "status": "publication_not_identified",

                        "research": research,

                        "verification": None,

                        "verification_status": "needs_manual_review"

                    })

                    continue

                # Retrieve evidence from publication

                evidence = retrieve_evidence(
                    claim_text,
                    best_match
                )

                passages = (
                    evidence.get("passages", [])
                    if isinstance(evidence, dict)
                    else []
                )

                verification = None

                if (
                    isinstance(evidence, dict)
                    and evidence.get("success")
                    and isinstance(passages, list)
                    and passages
                ):

                    verification = verify_claim_against_passages(
                        claim_text,
                        passages
                    )

                    verification_status = (
                        verification.get(
                            "status",
                            "needs_manual_review"
                        )
                        if isinstance(verification, dict)
                        else "needs_manual_review"
                    )

                else:

                    verification_status = "insufficient_evidence"

                claim_result["evidence_results"].append({

                    "reference_number": reference_number,

                    "reference_text": reference_text,

                    "publication": best_match,

                    "evidence": evidence,

                    "verification": verification,

                    "verification_status": verification_status

                })

            results.append(claim_result)

        # ------------------------------------------
        # VERIFICATION SUMMARY
        # ------------------------------------------

        total_evidence_sources = sum(
            len(item["evidence_results"])
            for item in results
        )

        verification_counts = {
            "supported": 0,
            "contradicted": 0,
            "insufficient_evidence": 0,
            "needs_manual_review": 0
        }

        for claim_item in results:

            for evidence_item in claim_item["evidence_results"]:

                status = evidence_item.get(
                    "verification_status",
                    "needs_manual_review"
                )

                if status in verification_counts:
                    verification_counts[status] += 1

                else:
                    verification_counts["needs_manual_review"] += 1

        print("\n========== AUTOMATIC VERIFICATION SUMMARY ==========")

        print("CLAIMS PROCESSED:", len(results))

        print("EVIDENCE SOURCES:", total_evidence_sources)

        print("VERIFICATION COUNTS:", verification_counts)

        print("=====================================================\n")

        return jsonify({

            "success": True,

            "total_claims_processed": len(results),

            "total_evidence_sources": total_evidence_sources,

            "verification_summary": verification_counts,

            "results": results,

            "message": (
                "Automatic evidence retrieval and AI assessment completed. "
                "Results require human review before being treated "
                "as scientific conclusions."
            )

        }), 200

    except Exception as error:

        print("\nAUTOMATIC EVIDENCE PIPELINE ERROR:", str(error))

        traceback.print_exc()

        return jsonify({
            "success": False,
            "error": str(error)
        }), 500


# ==================================================
# FILE SIZE ERROR HANDLER
# ==================================================

@app.errorhandler(413)
def file_too_large(error):

    return jsonify({
        "success": False,
        "error": "File exceeds the 15 MB upload limit"
    }), 413


# ==================================================
# INVALID REQUEST HANDLER
# ==================================================

@app.errorhandler(400)
def bad_request(error):

    return jsonify({
        "success": False,
        "error": "Invalid request"
    }), 400


# ==================================================
# START APPLICATION
# ==================================================

if __name__ == "__main__":

    app.run(
        host="127.0.0.1",
        port=5000,
        debug=True
    )
