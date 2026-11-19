
import { useState } from "react";

import {
  ShieldCheck,
  UploadCloud,
  FileText,
  Search,
  BrainCircuit,
  Quote,
  FileCheck,
  LoaderCircle,
  CheckCircle2,
  AlertCircle,
  X,
  ArrowRight,
  Activity,
  ExternalLink,
  RefreshCw,
  BookOpen,
  Microscope
} from "lucide-react";

import "./App.css";

const API_URL = "http://127.0.0.1:5000";

function App() {
  const [file, setFile] = useState(null);
  const [dragging, setDragging] = useState(false);

  const [loading, setLoading] = useState(false);
  const [researchLoading, setResearchLoading] = useState(false);
  const [evidenceLoading, setEvidenceLoading] = useState(false);

  const [error, setError] = useState("");
  const [researchError, setResearchError] = useState("");
  const [evidenceError, setEvidenceError] = useState("");

  const [result, setResult] = useState(null);
  const [researchData, setResearchData] = useState(null);
  const [evidenceData, setEvidenceData] = useState(null);

  const [activeTab, setActiveTab] = useState("claims");
  const [activePage, setActivePage] = useState("analyzer");

  // ==================================================
  // NORMALIZE REFERENCES
  // ==================================================

  const normalizeReferences = (data) => {
    if (Array.isArray(data?.references)) {
      return data.references;
    }

    if (Array.isArray(data?.analysis?.references)) {
      return data.analysis.references;
    }

    if (Array.isArray(data?.extracted_references)) {
      return data.extracted_references;
    }

    return [];
  };

  // ==================================================
  // REFERENCE COUNT
  // ==================================================

  const getReferenceCount = (data) => {
    const references = normalizeReferences(data);

    if (references.length > 0) {
      return references.length;
    }

    return (
      data?.reference_count ??
      data?.analysis?.total_references ??
      0
    );
  };

  // ==================================================
  // FILE UPLOAD
  // ==================================================

  const selectFile = (selectedFile) => {
    setError("");
    setResearchError("");
    setEvidenceError("");

    setResult(null);
    setResearchData(null);
    setEvidenceData(null);

    if (!selectedFile) return;

    if (
      selectedFile.type !== "application/pdf" &&
      !selectedFile.name.toLowerCase().endsWith(".pdf")
    ) {
      setError("Please upload a PDF document.");
      return;
    }

    if (selectedFile.size > 15 * 1024 * 1024) {
      setError("Maximum file size is 15 MB.");
      return;
    }

    setFile(selectedFile);
  };

  // ==================================================
  // DOCUMENT ANALYSIS
  // ==================================================

  const analyzeDocument = async () => {
    if (!file) {
      setError("Please select a research paper first.");
      return;
    }

    setLoading(true);

    setError("");
    setResearchError("");
    setEvidenceError("");

    setResult(null);
    setResearchData(null);
    setEvidenceData(null);

    const formData = new FormData();
    formData.append("file", file);

    try {
      const response = await fetch(`${API_URL}/api/analyze`, {
        method: "POST",
        body: formData
      });

      const data = await response.json();

      console.log("========== DOCUMENT ANALYSIS ==========");
      console.log("API RESPONSE:", data);
      console.log("REFERENCES:", data.references);
      console.log("IN-TEXT CITATIONS:", data.intext_citations);
      console.log("CLAIM LINKS:", data.claim_citation_links);
      console.log("ANALYSIS:", data.analysis);
      console.log("=======================================");

      if (!response.ok || !data.success) {
        throw new Error(data.error || "Document analysis failed.");
      }

      const extractedReferences = normalizeReferences(data);

      const normalizedData = {
        ...data,

        references: extractedReferences,

        analysis: {
          ...(data.analysis || {}),

          total_claims:
            data.analysis?.total_claims ??
            data.claims?.length ??
            0,

          total_citations:
            data.analysis?.total_citations ??
            data.citations?.length ??
            0,

          total_references:
            extractedReferences.length ||
            data.analysis?.total_references ||
            data.reference_count ||
            0
        },

        claims: Array.isArray(data.claims)
          ? data.claims
          : [],

        citations: Array.isArray(data.citations)
          ? data.citations
          : [],

        intext_citations: Array.isArray(data.intext_citations)
          ? data.intext_citations
          : [],

        claim_citation_links: Array.isArray(data.claim_citation_links)
          ? data.claim_citation_links
          : [],

        preview: data.preview || ""
      };

      setResult(normalizedData);

      setActiveTab("claims");
      setActivePage("analyzer");

    } catch (err) {
      console.error("DOCUMENT ANALYSIS ERROR:", err);

      setError(
        err.message || "Unable to connect to the backend."
      );

    } finally {
      setLoading(false);
    }
  };

  // ==================================================
  // REFERENCE TEXT
  // ==================================================

  const getReferenceText = (reference) => {
    if (typeof reference === "string") {
      return reference;
    }

    if (!reference) {
      return "Reference text unavailable";
    }

    return (
      reference.reference_text ||
      reference.reference ||
      reference.text ||
      reference.raw ||
      reference.entry ||
      "Reference text unavailable"
    );
  };

  // ==================================================
  // CITATION INTELLIGENCE HELPERS
  // ==================================================

  const getCitationLabel = (item) => {
    if (typeof item === "string") return item;

    if (!item) return "Citation unavailable";

    return (
      item.citation_text ||
      item.citation ||
      item.text ||
      item.raw ||
      item.value ||
      "Citation unavailable"
    );
  };

  const getCitationNumber = (item) => {
    if (typeof item === "number") return item;

    const directNumber =
      item?.reference_number ??
      item?.citation_number ??
      item?.number ??
      item?.matched_reference?.number ??
      item?.matched_reference?.reference_number;

    if (directNumber !== undefined && directNumber !== null) {
      const parsed = Number(directNumber);

      if (Number.isFinite(parsed)) {
        return parsed;
      }
    }

    const label = getCitationLabel(item);
    const match = label.match(/\[?\s*(\d{1,4})\s*\]?/);

    return match ? Number(match[1]) : null;
  };

  const getCitationMappingStatus = (item) => {
    const status = String(
      item?.mapping_status || item?.status || ""
    ).toLowerCase();

    if (
      status === "matched" ||
      status === "linked" ||
      item?.matched_reference
    ) {
      return "matched";
    }

    return "unmatched";
  };

  const getCitationRows = () => {
    if (!result) return [];

    if (Array.isArray(result.intext_citations)) {
      return result.intext_citations;
    }

    return [];
  };

  const getCitationSummary = () => {
    const rows = getCitationRows();

    const matched = rows.filter(
      (item) => getCitationMappingStatus(item) === "matched"
    );

    const matchedNumbers = new Set(
      matched
        .map((item) => getCitationNumber(item))
        .filter((number) => number !== null)
    );

    const references = normalizeReferences(result);

    const unusedReferences = references.filter((reference, index) => {
      const number =
        reference?.number ??
        reference?.reference_number ??
        index + 1;

      return !matchedNumbers.has(Number(number));
    });

    const claimLinks = result?.claim_citation_links || [];

    const unlinkedClaims = claimLinks.filter(
      (item) => item.link_status !== "linked"
    );

    return {
      total: rows.length,
      matched: matched.length,
      unmatched: rows.length - matched.length,
      unusedReferences: unusedReferences.length,
      unlinkedClaims: unlinkedClaims.length,
      references: unusedReferences,
      claims: unlinkedClaims
    };
  };

  // ==================================================
  // CROSSREF RESULTS
  // ==================================================

  const getResearchResults = () => {
    if (!researchData) return [];

    if (Array.isArray(researchData.results)) {
      return researchData.results;
    }

    if (Array.isArray(researchData.candidate_matches)) {
      return researchData.candidate_matches;
    }

    return [];
  };

  // ==================================================
  // RESEARCH CANDIDATES
  // ==================================================

  const getCandidates = (item) => {
    const research = item?.research || item;

    if (!research) return [];

    if (Array.isArray(research.candidates)) {
      return research.candidates;
    }

    if (research.best_match) {
      return [research.best_match];
    }

    if (research.title || research.doi) {
      return [research];
    }

    return [];
  };

  // ==================================================
  // MATCH STATUS
  // ==================================================

  const getMatchStatus = (item) => {
    const research = item?.research || item;

    const status =
      research?.status ||
      item?.status;

    if (status === "candidate_found") {
      return {
        label: "Candidate found",
        className: "match-status"
      };
    }

    return {
      label: "Review needed",
      className: "review-status"
    };
  };

  // ==================================================
  // RESEARCH RETRIEVAL
  // ==================================================

  const retrieveResearch = async () => {
    if (!result) return;

    const references = normalizeReferences(result);

    if (references.length === 0) {
      setResearchError(
        "No references were extracted from this document."
      );
      return;
    }

    setResearchLoading(true);
    setResearchError("");
    setResearchData(null);

    try {
      const response = await fetch(
        `${API_URL}/api/research/retrieve`,
        {
          method: "POST",
          headers: {
            "Content-Type": "application/json"
          },
          body: JSON.stringify({
            references: references.slice(0, 20)
          })
        }
      );

      const data = await response.json();

      if (!response.ok || !data.success) {
        throw new Error(
          data.error || "Research retrieval failed."
        );
      }

      console.log("CROSSREF RESPONSE:", data);

      setResearchData(data);
      setActivePage("research");

    } catch (err) {
      console.error("RESEARCH RETRIEVAL ERROR:", err);

      setResearchError(
        err.message || "Unable to retrieve publications."
      );

    } finally {
      setResearchLoading(false);
    }
  };

  // ==================================================
  // STATUS HELPERS
  // ==================================================

  const getVerificationLabel = (status) => {
    const labels = {
      supported: "Supported",
      contradicted: "Contradicted",
      insufficient_evidence: "Insufficient Evidence",
      needs_manual_review: "Manual Review",
      publication_not_identified: "Publication Not Identified",
      no_open_access_pdf: "Full Text Unavailable",
      pdf_retrieved_no_relevant_passages: "No Relevant Passages",
      evidence_passages_found: "Evidence Retrieved",
      not_verified: "Not Verified"
    };

    return labels[status] || "Manual Review";
  };

  const getVerificationClass = (status) => {
    const classes = {
      supported: "verification-supported",
      contradicted: "verification-contradicted",
      insufficient_evidence: "verification-insufficient",
      needs_manual_review: "verification-review",
      publication_not_identified: "verification-review",
      no_open_access_pdf: "verification-review",
      pdf_retrieved_no_relevant_passages: "verification-insufficient",
      evidence_passages_found: "verification-review",
      not_verified: "verification-review"
    };

    return classes[status] || "verification-review";
  };

  // ==================================================
  // AUTOMATIC EVIDENCE ANALYSIS
  // ==================================================

  const analyzeEvidence = async () => {
    if (!result) {
      setEvidenceError("Analyze a research document first.");
      return;
    }

    const references = normalizeReferences(result);
    const claimLinks = result.claim_citation_links || [];

    if (claimLinks.length === 0) {
      setEvidenceError(
        "No claim-to-citation links are available. Analyze a document with claims and citations first."
      );
      return;
    }

    if (references.length === 0) {
      setEvidenceError(
        "No references were extracted from this document."
      );
      return;
    }

    setEvidenceLoading(true);
    setEvidenceError("");
    setEvidenceData(null);

    try {
      const evidenceResponse = await fetch(
        `${API_URL}/api/evidence/analyze`,
        {
          method: "POST",
          headers: {
            "Content-Type": "application/json"
          },
          body: JSON.stringify({
            claim_citation_links: claimLinks,
            references: references
          })
        }
      );

      const evidenceResult = await evidenceResponse.json();

      if (!evidenceResponse.ok || !evidenceResult.success) {
        throw new Error(
          evidenceResult.error ||
          "Automatic evidence retrieval failed."
        );
      }

      console.log(
        "AUTOMATIC EVIDENCE RESPONSE:",
        evidenceResult
      );

      const verifiedResults = [];

      for (const claimItem of evidenceResult.results || []) {
        const updatedClaim = {
          ...claimItem,
          evidence_results: []
        };

        for (const sourceItem of claimItem.evidence_results || []) {
          const evidence = sourceItem.evidence || {};

          const passages = Array.isArray(evidence.passages)
            ? evidence.passages
            : [];

          let verification = {
            success: true,
            status: "insufficient_evidence",
            total_passages: passages.length,
            assessments: [],
            message: "No evidence passages were available for verification."
          };

          if (
            evidence.success !== false &&
            passages.length > 0
          ) {
            try {
              const verifyResponse = await fetch(
                `${API_URL}/api/evidence/verify`,
                {
                  method: "POST",
                  headers: {
                    "Content-Type": "application/json"
                  },
                  body: JSON.stringify({
                    claim: claimItem.claim,
                    passages: passages.slice(0, 20)
                  })
                }
              );

              const verifyData = await verifyResponse.json();

              if (!verifyResponse.ok || !verifyData.success) {
                throw new Error(
                  verifyData.error || "AI verification failed."
                );
              }

              verification =
                verifyData.verification || verification;

            } catch (verifyError) {
              console.error(
                "INDIVIDUAL VERIFICATION ERROR:",
                verifyError
              );

              verification = {
                success: false,
                status: "needs_manual_review",
                assessments: [],
                error: verifyError.message,
                message: "AI verification could not be completed."
              };
            }
          }

          updatedClaim.evidence_results.push({
            ...sourceItem,
            verification
          });
        }

        verifiedResults.push(updatedClaim);
      }

      const finalData = {
        ...evidenceResult,
        results: verifiedResults,
        verification_completed: true
      };

      console.log(
        "FINAL EVIDENCE VERIFICATION:",
        finalData
      );

      setEvidenceData(finalData);
      setActivePage("evidence");

    } catch (err) {
      console.error("EVIDENCE ANALYSIS ERROR:", err);

      setEvidenceError(
        err.message || "Unable to analyze research evidence."
      );

    } finally {
      setEvidenceLoading(false);
    }
  };

  // ==================================================
  // EVIDENCE SUMMARY
  // ==================================================

  const getEvidenceSummary = () => {
    const summary = {
      total: 0,
      supported: 0,
      contradicted: 0,
      insufficient: 0,
      review: 0
    };

    const results = evidenceData?.results || [];

    results.forEach((claimItem) => {
      const sources = claimItem.evidence_results || [];

      sources.forEach((source) => {
        summary.total += 1;

        const status =
          source.verification?.status ||
          source.verification_status ||
          "needs_manual_review";

        if (status === "supported") {
          summary.supported += 1;
        } else if (status === "contradicted") {
          summary.contradicted += 1;
        } else if (status === "insufficient_evidence") {
          summary.insufficient += 1;
        } else {
          summary.review += 1;
        }
      });
    });

    return summary;
  };

  // ==================================================
  // EVIDENCE INTELLIGENCE PAGE
  // ==================================================

  const renderEvidencePage = () => {
    const evidenceResults = evidenceData?.results || [];
    const summary = getEvidenceSummary();
    const hasResults = evidenceResults.length > 0;

    return (
      <section className="evidence-section">

        <div className="page-heading">
          <div>
            <span className="eyebrow">
              <BrainCircuit size={15} />
              AI-POWERED EVIDENCE VERIFICATION
            </span>

            <h1>Evidence Intelligence</h1>

            <p>
              Compare research claims with retrieved publication
              passages using natural language inference.
            </p>
          </div>
        </div>

        <div className="evidence-toolbar">
          <div>
            <h2>Research Verification Engine</h2>

            <p>
              Retrieve source passages and assess whether they
              support, contradict or provide insufficient evidence
              for extracted claims.
            </p>
          </div>

          <button
            className="analyze-button"
            onClick={analyzeEvidence}
            disabled={evidenceLoading || !result}
          >
            {evidenceLoading ? (
              <>
                <LoaderCircle className="spin" size={17} />
                Processing...
              </>
            ) : (
              <>
                <RefreshCw size={17} />
                Run Verification
              </>
            )}
          </button>
        </div>

        {evidenceError && (
          <div className="error-message">
            <AlertCircle size={18} />
            {evidenceError}
          </div>
        )}

        {!evidenceData && !evidenceLoading && (
          <div className="evidence-empty">
            <BrainCircuit size={38} />

            <h3>Ready to verify research claims</h3>

            <p>
              {result
                ? `${result.analysis?.total_claims || 0} claims and ${getReferenceCount(result)} references are available for analysis.`
                : "Upload and analyze a research PDF before starting evidence verification."}
            </p>
          </div>
        )}

        {evidenceLoading && (
          <div className="evidence-empty">
            <LoaderCircle className="spin" size={35} />

            <h3>Analyzing research evidence...</h3>

            <p>
              Retrieving publication records, extracting passages
              and running AI verification. This may take some time.
            </p>
          </div>
        )}

        {evidenceData && (
          <>
            <div className="evidence-stats">

              <div className="evidence-stat-card">
                <BookOpen size={23} color="#b58b3c" />
                <span>Evidence Sources</span>
                <h2>{summary.total}</h2>
              </div>

              <div className="evidence-stat-card">
                <CheckCircle2 size={23} color="#397b53" />
                <span>Supported</span>
                <h2>{summary.supported}</h2>
              </div>

              <div className="evidence-stat-card">
                <AlertCircle size={23} color="#b44747" />
                <span>Contradicted</span>
                <h2>{summary.contradicted}</h2>
              </div>

              <div className="evidence-stat-card">
                <Microscope size={23} color="#9b7935" />
                <span>Manual Review / Other</span>
                <h2>
                  {summary.review + summary.insufficient}
                </h2>
              </div>

            </div>

            <div className="evidence-overview">
              <div>
                <span>Claims Processed</span>
                <h2>
                  {evidenceData.total_claims_processed ??
                    evidenceResults.length}
                </h2>
              </div>

              <div>
                <span>Verification Sources</span>
                <h2>{summary.total}</h2>
              </div>
            </div>

            <div className="evidence-results-card">

              <div className="evidence-results-heading">
                <h2>Claim Verification Results</h2>

                <p>
                  Each result shows its publication source,
                  retrieved evidence and AI assessment.
                </p>
              </div>

              {!hasResults ? (
                <div className="empty-state">
                  No claim results were returned by the backend.
                </div>
              ) : (
                evidenceResults.map((claimItem, index) => (
                  <div
                    className="evidence-claim"
                    key={claimItem.claim_id ?? index}
                  >

                    <div className="evidence-claim-heading">

                      <span className="research-number">
                        {String(
                          claimItem.claim_id ?? index + 1
                        ).padStart(2, "0")}
                      </span>

                      <div>
                        <span className="claim-label">
                          RESEARCH CLAIM
                        </span>

                        <p>{claimItem.claim}</p>
                      </div>

                    </div>

                    {!claimItem.evidence_results?.length ? (
                      <div className="evidence-empty-result">
                        <AlertCircle size={17} />

                        No matched reference or evidence source
                        was available for this claim.
                      </div>
                    ) : (
                      claimItem.evidence_results.map(
                        (source, sourceIndex) => {
                          const publication = source.publication || {};
                          const evidence = source.evidence || {};
                          const verification = source.verification || {};

                          const status =
                            verification.status ||
                            source.verification_status ||
                            "needs_manual_review";

                          const assessments =
                            verification.assessments || [];

                          return (
                            <div
                              className="evidence-source"
                              key={sourceIndex}
                            >

                              <div className="evidence-source-heading">
                                <span className="source-label">
                                  SOURCE {sourceIndex + 1}
                                </span>

                                <span
                                  className={`verification-badge ${getVerificationClass(status)}`}
                                >
                                  {getVerificationLabel(status)}
                                </span>
                              </div>

                              <h3>
                                {publication.title ||
                                  "Publication details unavailable"}
                              </h3>

                              {publication.authors?.length > 0 && (
                                <p className="source-meta">
                                  <strong>Authors:</strong>{" "}
                                  {publication.authors.join(", ")}
                                </p>
                              )}

                              {publication.journal && (
                                <p className="source-meta">
                                  <strong>Journal:</strong>{" "}
                                  {publication.journal}
                                </p>
                              )}

                              {publication.year && (
                                <p className="source-meta">
                                  <strong>Year:</strong>{" "}
                                  {publication.year}
                                </p>
                              )}

                              {publication.doi && (
                                <p className="source-meta">
                                  <strong>DOI:</strong>{" "}
                                  <a
                                    href={`https://doi.org/${publication.doi}`}
                                    target="_blank"
                                    rel="noreferrer"
                                  >
                                    {publication.doi}
                                    <ExternalLink size={12} />
                                  </a>
                                </p>
                              )}

                              {source.reference_number && (
                                <p className="source-meta">
                                  <strong>Reference number:</strong>{" "}
                                  {source.reference_number}
                                </p>
                              )}

                              <div className="passage-list">
                                <h4>
                                  Retrieved Evidence Passages
                                </h4>

                                {assessments.length > 0 ? (
                                  assessments.map(
                                    (item, passageIndex) => {
                                      const assessment =
                                        item.assessment || {};

                                      const passageStatus =
                                        assessment.status ||
                                        "needs_manual_review";

                                      return (
                                        <div
                                          className="passage-card"
                                          key={passageIndex}
                                        >

                                          <div className="passage-heading">
                                            <span>
                                              PAGE {item.page ?? "N/A"}
                                            </span>

                                            <span
                                              className={`verification-badge ${getVerificationClass(passageStatus)}`}
                                            >
                                              {getVerificationLabel(passageStatus)}
                                            </span>
                                          </div>

                                          <p>{item.passage}</p>

                                          {typeof assessment.confidence === "number" && (
                                            <div className="confidence-row">
                                              <span>AI confidence</span>

                                              <strong>
                                                {(assessment.confidence * 100).toFixed(1)}%
                                              </strong>
                                            </div>
                                          )}

                                          {assessment.scores && (
                                            <div className="nli-scores">
                                              {Object.entries(
                                                assessment.scores
                                              ).map(([label, score]) => (
                                                <span key={label}>
                                                  {label}:{" "}
                                                  {(score * 100).toFixed(1)}%
                                                </span>
                                              ))}
                                            </div>
                                          )}

                                        </div>
                                      );
                                    }
                                  )
                                ) : (
                                  <div className="evidence-empty-result">
                                    <AlertCircle size={16} />

                                    {evidence.message ||
                                      verification.message ||
                                      "No passages were available for assessment."}
                                  </div>
                                )}
                              </div>

                              {evidence.status && (
                                <p className="verification-note">
                                  Evidence retrieval status:{" "}
                                  {getVerificationLabel(evidence.status)}
                                </p>
                              )}

                              {verification.message && (
                                <p className="verification-note">
                                  {verification.message}
                                </p>
                              )}

                              {evidence.error && (
                                <p className="verification-note">
                                  Retrieval information: {evidence.error}
                                </p>
                              )}

                            </div>
                          );
                        }
                      )
                    )}

                  </div>
                ))
              )}

            </div>

            <div className="notice">
              <AlertCircle size={17} />

              AI verification is an automated assessment of retrieved
              passages, not proof of scientific truth. Context,
              methodology and the complete publication should be
              reviewed by a human researcher before accepting a result.
            </div>
          </>
        )}
      </section>
    );
  };

  // ==================================================
  // RESEARCH FINDER PAGE
  // ==================================================

  const renderResearchPage = () => {
    const references = normalizeReferences(result);
    const researchResults = getResearchResults();

    return (
      <section className="research-section">

        <div className="page-heading">
          <div>
            <span className="eyebrow">
              <Search size={15} />
              CROSSREF PUBLICATION DISCOVERY
            </span>

            <h1>Research Finder</h1>

            <p>
              Discover publication records corresponding to
              references extracted from your research paper.
            </p>
          </div>
        </div>

        <div className="research-summary">

          <div>
            <FileText size={23} />
            <span>Extracted References</span>
            <h2>{references.length}</h2>
          </div>

          <div>
            <Search size={23} />
            <span>References Submitted</span>
            <h2>
              {researchData?.total_references ??
                researchResults.length}
            </h2>
          </div>

          <div>
            <CheckCircle2 size={23} />
            <span>Results Returned</span>
            <h2>{researchResults.length}</h2>
          </div>

        </div>

        <div className="results-card research-card">

          <div className="research-toolbar">
            <div>
              <h2>Publication Matching</h2>

              <p>
                Search publication metadata using Crossref.
              </p>
            </div>

            <button
              className="analyze-button"
              onClick={retrieveResearch}
              disabled={
                researchLoading || references.length === 0
              }
            >
              {researchLoading ? (
                <>
                  <LoaderCircle className="spin" size={17} />
                  Searching...
                </>
              ) : (
                <>
                  <RefreshCw size={17} />
                  Retrieve Matches
                </>
              )}
            </button>
          </div>

          {researchError && (
            <div className="error-message research-error">
              <AlertCircle size={18} />
              {researchError}
            </div>
          )}

          {!researchData && !researchLoading && (
            <div className="empty-state research-empty">
              <Search size={32} />

              <h3>Ready to find publications</h3>

              <p>
                {references.length > 0
                  ? `${references.length} references are available for retrieval.`
                  : "Analyze a research PDF containing references first."}
              </p>
            </div>
          )}

          {researchLoading && (
            <div className="empty-state research-empty">
              <LoaderCircle className="spin" size={30} />
              <p>Searching publication records...</p>
            </div>
          )}

          {researchData && (
            <div className="research-results">

              {researchResults.length === 0 ? (
                <p className="empty-state">
                  No candidate publication records were returned.
                </p>
              ) : (
                researchResults.map((item, index) => {
                  const candidates = getCandidates(item);
                  const status = getMatchStatus(item);

                  return (
                    <div className="research-item" key={index}>

                      <div className="research-item-heading">

                        <span className="research-number">
                          {String(
                            item.reference_number || index + 1
                          ).padStart(2, "0")}
                        </span>

                        <div className="research-item-content">

                          <span className="claim-label">
                            ORIGINAL REFERENCE
                          </span>

                          <p className="original-reference">
                            {getReferenceText(item)}
                          </p>

                        </div>

                        <span className={status.className}>
                          {status.label}
                        </span>

                      </div>

                      {candidates.length === 0 ? (
                        <p className="empty-state">
                          No publication candidate was identified.
                        </p>
                      ) : (
                        candidates.map((candidate, candidateIndex) => (

                          <div
                            className="publication-card"
                            key={candidateIndex}
                          >

                            <h3>
                              {candidate.title ||
                                "Publication title unavailable"}
                            </h3>

                            {candidate.authors && (
                              <p>
                                <strong>Authors:</strong>{" "}

                                {Array.isArray(candidate.authors)
                                  ? candidate.authors
                                      .map((author) => {
                                        if (typeof author === "string") {
                                          return author;
                                        }

                                        return (
                                          author.name ||
                                          [
                                            author.given,
                                            author.family
                                          ]
                                            .filter(Boolean)
                                            .join(" ")
                                        );
                                      })
                                      .join(", ")
                                  : candidate.authors}
                              </p>
                            )}

                            {candidate.journal && (
                              <p>
                                <strong>Journal:</strong>{" "}
                                {candidate.journal}
                              </p>
                            )}

                            {candidate.year && (
                              <p>
                                <strong>Year:</strong>{" "}
                                {candidate.year}
                              </p>
                            )}

                            {candidate.publisher && (
                              <p>
                                <strong>Publisher:</strong>{" "}
                                {candidate.publisher}
                              </p>
                            )}

                            {candidate.doi && (
                              <p>
                                <strong>DOI:</strong>{" "}

                                <a
                                  href={`https://doi.org/${candidate.doi}`}
                                  target="_blank"
                                  rel="noreferrer"
                                >
                                  {candidate.doi}
                                  <ExternalLink size={13} />
                                </a>
                              </p>
                            )}

                            {typeof candidate.similarity === "number" && (
                              <p>
                                <strong>Text similarity:</strong>{" "}
                                {(candidate.similarity * 100).toFixed(1)}%
                              </p>
                            )}

                            {candidate.url && (
                              <a
                                className="publication-link"
                                href={candidate.url}
                                target="_blank"
                                rel="noreferrer"
                              >
                                View publication
                                <ExternalLink size={14} />
                              </a>
                            )}

                          </div>

                        ))
                      )}

                    </div>
                  );
                })
              )}

            </div>
          )}

        </div>

        <div className="notice">
          <AlertCircle size={17} />

          Crossref returns bibliographic metadata candidates.
          A matching title or DOI does not prove that a publication
          supports a scientific claim. Independent evidence
          verification is required.
        </div>

      </section>
    );
  };

  // ==================================================
  // CITATION INTELLIGENCE PAGE
  // ==================================================

  const renderCitationPage = () => {
    const rows = getCitationRows();
    const summary = getCitationSummary();
    const references = normalizeReferences(result);

    return (
      <section className="citation-intelligence-section">

        <div className="page-heading">
          <div>
            <span className="eyebrow">
              <Quote size={15} />
              CITATION MAPPING & VALIDATION
            </span>

            <h1>Citation Intelligence</h1>

            <p>
              Analyze in-text citations, validate reference
              connections and identify missing or unused references.
            </p>
          </div>
        </div>

        {!result ? (
          <div className="evidence-empty">
            <Quote size={38} />

            <h3>No research document analyzed</h3>

            <p>
              Upload and analyze a research PDF first to explore
              its citation relationships.
            </p>

            <button
              className="analyze-button"
              onClick={() => setActivePage("analyzer")}
            >
              Open Document Analyzer
              <ArrowRight size={17} />
            </button>
          </div>
        ) : (
          <>
            <div className="evidence-stats">

              <div className="evidence-stat-card">
                <Quote size={23} color="#b58b3c" />
                <span>Total In-text Citations</span>
                <h2>{summary.total}</h2>
              </div>

              <div className="evidence-stat-card">
                <CheckCircle2 size={23} color="#397b53" />
                <span>Matched Citations</span>
                <h2>{summary.matched}</h2>
              </div>

              <div className="evidence-stat-card">
                <AlertCircle size={23} color="#b44747" />
                <span>Unmatched Citations</span>
                <h2>{summary.unmatched}</h2>
              </div>

              <div className="evidence-stat-card">
                <BookOpen size={23} color="#9b7935" />
                <span>Unused References</span>
                <h2>{summary.unusedReferences}</h2>
              </div>

            </div>

            <div className="evidence-overview">
              <div>
                <span>Reference Entries</span>
                <h2>{references.length}</h2>
              </div>

              <div>
                <span>Claims Without Linked References</span>
                <h2>{summary.unlinkedClaims}</h2>
              </div>
            </div>

            <div className="evidence-results-card">

              <div className="evidence-results-heading">
                <h2>Citation-to-Reference Mapping</h2>

                <p>
                  Each in-text citation is checked against the
                  extracted reference list.
                </p>
              </div>

              {rows.length === 0 ? (
                <div className="empty-state">
                  No citation mapping data was returned.
                  Check that the backend provides the
                  <strong> intext_citations </strong>
                  field.
                </div>
              ) : (
                rows.map((item, index) => {
                  const status = getCitationMappingStatus(item);
                  const number = getCitationNumber(item);

                  const reference = references.find(
                    (ref, refIndex) => {
                      const refNumber =
                        ref?.number ??
                        ref?.reference_number ??
                        refIndex + 1;

                      return Number(refNumber) === Number(number);
                    }
                  );

                  const matchedText =
                    item?.matched_reference?.text ||
                    item?.matched_reference?.reference_text ||
                    item?.reference_text ||
                    item?.matched_reference_text ||
                    (reference ? getReferenceText(reference) : "");

                  return (
                    <div className="evidence-claim" key={index}>

                      <div className="evidence-source-heading">
                        <span className="source-label">
                          CITATION {String(index + 1).padStart(2, "0")}
                        </span>

                        <span
                          className={`verification-badge ${
                            status === "matched"
                              ? "verification-supported"
                              : "verification-contradicted"
                          }`}
                        >
                          {status === "matched" ? "Matched" : "Unmatched"}
                        </span>
                      </div>

                      <div className="citation-item">
                        <Quote size={18} />

                        <strong>
                          {getCitationLabel(item)}
                        </strong>
                      </div>

                      <div className="citation-mapping-detail">
                        <span>REFERENCE CONNECTION</span>

                        {status === "matched" ? (
                          <p>
                            {matchedText ||
                              `Reference [${number ?? "?"}] matched`}
                          </p>
                        ) : (
                          <p>
                            No matching reference was identified
                            for this citation.
                          </p>
                        )}
                      </div>

                    </div>
                  );
                })
              )}

            </div>

            <div className="evidence-results-card">

              <div className="evidence-results-heading">
                <h2>Unused References</h2>

                <p>
                  Reference entries that were not found among
                  the successfully matched in-text citations.
                </p>
              </div>

              {summary.references.length === 0 ? (
                <div className="empty-state">
                  No unused references were detected.
                </div>
              ) : (
                summary.references.map((reference, index) => (
                  <div className="citation-item" key={index}>
                    <FileCheck size={18} />
                    <span>{getReferenceText(reference)}</span>
                  </div>
                ))
              )}

            </div>

            <div className="evidence-results-card">

              <div className="evidence-results-heading">
                <h2>Claims Without Citation Links</h2>

                <p>
                  Potential research claims for which no matching
                  reference was linked.
                </p>
              </div>

              {summary.claims.length === 0 ? (
                <div className="empty-state">
                  All detected claims have at least one linked reference.
                </div>
              ) : (
                summary.claims.map((claim, index) => (
                  <div className="claim-item" key={index}>
                    <div className="claim-number">
                      {String(index + 1).padStart(2, "0")}
                    </div>

                    <div>
                      <span className="claim-label">
                        UNLINKED RESEARCH CLAIM
                      </span>

                      <p>{claim.claim}</p>
                    </div>
                  </div>
                ))
              )}

            </div>

            <div className="notice">
              <AlertCircle size={17} />

              Citation matching checks whether in-text citations
              correspond to entries in the reference list. A
              successful match does not establish that the cited
              publication supports the claim.
            </div>
          </>
        )}

      </section>
    );
  };


  // ==================================================
  // VERIFICATION REPORTS PAGE
  // ==================================================

  const renderReportPage = () => {
    const results = evidenceData?.results || [];
    const citationSummary = getCitationSummary();
    const summary = getEvidenceSummary();

    // Determine one overall status for each claim.
    const getClaimStatus = (claim) => {
      const sources = claim.evidence_results || [];

      const statuses = sources.map(
        (source) =>
          source.verification?.status ||
          source.verification_status ||
          "needs_manual_review"
      );

      if (statuses.includes("contradicted")) {
        return "contradicted";
      }

      if (
        statuses.includes("supported") &&
        statuses.includes("contradicted")
      ) {
        return "needs_manual_review";
      }

      if (statuses.includes("supported")) {
        return "supported";
      }

      if (statuses.includes("insufficient_evidence")) {
        return "insufficient_evidence";
      }

      return "needs_manual_review";
    };

    const claimCounts = {
      supported: 0,
      contradicted: 0,
      insufficient_evidence: 0,
      needs_manual_review: 0
    };

    results.forEach((claim) => {
      claimCounts[getClaimStatus(claim)] += 1;
    });

    const handlePrintReport = () => {
      window.print();
    };

    return (
      <section className="report-section">

        <div className="page-heading">
          <div>
            <span className="eyebrow">
              <FileCheck size={15} />
              RESEARCH VERIFICATION SUMMARY
            </span>

            <h1>Verification Reports</h1>

            <p>
              Review claim assessments, publication evidence,
              citation integrity and verification results.
            </p>
          </div>

          {evidenceData && (
            <button
              className="analyze-button"
              onClick={handlePrintReport}
            >
              <FileText size={17} />
              Download PDF
            </button>
          )}
        </div>

        {!result ? (
          <div className="evidence-empty">
            <FileCheck size={38} />

            <h3>No research document available</h3>

            <p>
              Upload and analyze a research PDF to create a
              verification report.
            </p>

            <button
              className="analyze-button"
              onClick={() => setActivePage("analyzer")}
            >
              Open Document Analyzer
              <ArrowRight size={17} />
            </button>
          </div>
        ) : !evidenceData ? (
          <div className="evidence-empty">
            <BrainCircuit size={38} />

            <h3>Verification has not been completed</h3>

            <p>
              Your document has been analyzed, but an evidence
              verification report is not available yet. Run
              Evidence Intelligence first.
            </p>

            <button
              className="analyze-button"
              onClick={analyzeEvidence}
              disabled={evidenceLoading}
            >
              {evidenceLoading ? (
                <>
                  <LoaderCircle className="spin" size={17} />
                  Processing...
                </>
              ) : (
                <>
                  <BrainCircuit size={17} />
                  Run Evidence Verification
                </>
              )}
            </button>

            {evidenceError && (
              <div className="error-message">
                <AlertCircle size={18} />
                {evidenceError}
              </div>
            )}
          </div>
        ) : (
          <div className="report-document">

            {/* REPORT HEADER */}

            <div className="report-header">
              <div className="report-brand">
                <ShieldCheck size={30} />

                <div>
                  <h2>CiteVerify AI</h2>
                  <span>Research Trust & Evidence Intelligence</span>
                </div>
              </div>

              <div className="report-meta">
                <span>VERIFICATION REPORT</span>
                <strong>
                  {new Date().toLocaleDateString()}
                </strong>
              </div>
            </div>

            <div className="report-file">
              <span className="claim-label">
                ANALYZED DOCUMENT
              </span>

              <h2>
                {result.document?.name || file?.name || "Research PDF"}
              </h2>

              <p>
                {result.document?.pages ?? 0} pages ·{" "}
                {(result.document?.word_count ?? 0).toLocaleString()} words
              </p>
            </div>

            {/* OVERALL STATISTICS */}

            <div className="evidence-results-heading">
              <h2>Verification Overview</h2>

              <p>
                Summary of claim-level assessments returned by
                the evidence verification process.
              </p>
            </div>

            <div className="evidence-stats">

              <div className="evidence-stat-card">
                <FileText size={23} />
                <span>Claims Processed</span>
                <h2>{results.length}</h2>
              </div>

              <div className="evidence-stat-card">
                <CheckCircle2 size={23} color="#397b53" />
                <span>Supported Claims</span>
                <h2>{claimCounts.supported}</h2>
              </div>

              <div className="evidence-stat-card">
                <AlertCircle size={23} color="#b44747" />
                <span>Contradicted Claims</span>
                <h2>{claimCounts.contradicted}</h2>
              </div>

              <div className="evidence-stat-card">
                <Microscope size={23} color="#9b7935" />
                <span>Insufficient Evidence</span>
                <h2>{claimCounts.insufficient_evidence}</h2>
              </div>

              <div className="evidence-stat-card">
                <AlertCircle size={23} color="#9b7935" />
                <span>Manual Review</span>
                <h2>{claimCounts.needs_manual_review}</h2>
              </div>

            </div>

            {/* CITATION INTEGRITY */}

            <div className="evidence-results-card report-block">

              <div className="evidence-results-heading">
                <h2>Citation Integrity</h2>

                <p>
                  Bibliographic matching results from the uploaded
                  research document.
                </p>
              </div>

              <div className="report-citation-grid">

                <div>
                  <span>Total Citations</span>
                  <h2>{citationSummary.total}</h2>
                </div>

                <div>
                  <span>Matched Citations</span>
                  <h2>{citationSummary.matched}</h2>
                </div>

                <div>
                  <span>Unmatched Citations</span>
                  <h2>{citationSummary.unmatched}</h2>
                </div>

                <div>
                  <span>Reference Entries</span>
                  <h2>{getReferenceCount(result)}</h2>
                </div>

              </div>
            </div>

            {/* CLAIM RESULTS */}

            <div className="evidence-results-card report-block">

              <div className="evidence-results-heading">
                <h2>Detailed Claim Verification</h2>

                <p>
                  Individual research claims and their associated
                  source assessments.
                </p>
              </div>

              {results.length === 0 ? (
                <div className="empty-state">
                  No claim verification results were returned.
                </div>
              ) : (
                results.map((claim, index) => {
                  const status = getClaimStatus(claim);
                  const sources = claim.evidence_results || [];

                  return (
                    <div
                      className="evidence-claim report-claim"
                      key={claim.claim_id ?? index}
                    >

                      <div className="evidence-source-heading">
                        <span className="source-label">
                          CLAIM {String(index + 1).padStart(2, "0")}
                        </span>

                        <span
                          className={`verification-badge ${getVerificationClass(status)}`}
                        >
                          {getVerificationLabel(status)}
                        </span>
                      </div>

                      <p className="report-claim-text">
                        {claim.claim || "Claim text unavailable"}
                      </p>

                      {sources.length === 0 ? (
                        <div className="evidence-empty-result">
                          <AlertCircle size={16} />

                          No matched reference or evidence source
                          was available for this claim.
                        </div>
                      ) : (
                        sources.map((source, sourceIndex) => {
                          const publication = source.publication || {};
                          const evidence = source.evidence || {};
                          const verification = source.verification || {};
                          const assessments = verification.assessments || [];

                          const sourceStatus =
                            verification.status ||
                            source.verification_status ||
                            "needs_manual_review";

                          return (
                            <div
                              className="report-source"
                              key={sourceIndex}
                            >

                              <div className="evidence-source-heading">
                                <span className="source-label">
                                  EVIDENCE SOURCE {sourceIndex + 1}
                                </span>

                                <span
                                  className={`verification-badge ${getVerificationClass(sourceStatus)}`}
                                >
                                  {getVerificationLabel(sourceStatus)}
                                </span>
                              </div>

                              <h3>
                                {publication.title ||
                                  "Publication details unavailable"}
                              </h3>

                              {publication.authors?.length > 0 && (
                                <p className="source-meta">
                                  <strong>Authors:</strong>{" "}
                                  {publication.authors.join(", ")}
                                </p>
                              )}

                              {publication.journal && (
                                <p className="source-meta">
                                  <strong>Journal:</strong>{" "}
                                  {publication.journal}
                                </p>
                              )}

                              {publication.year && (
                                <p className="source-meta">
                                  <strong>Year:</strong>{" "}
                                  {publication.year}
                                </p>
                              )}

                              {publication.doi && (
                                <p className="source-meta">
                                  <strong>DOI:</strong>{" "}
                                  <a
                                    href={`https://doi.org/${publication.doi}`}
                                    target="_blank"
                                    rel="noreferrer"
                                  >
                                    {publication.doi}
                                    <ExternalLink size={12} />
                                  </a>
                                </p>
                              )}

                              {source.reference_number && (
                                <p className="source-meta">
                                  <strong>Reference:</strong>{" "}
                                  [{source.reference_number}]
                                </p>
                              )}

                              <div className="report-passages">
                                <h4>Evidence Passages</h4>

                                {assessments.length > 0 ? (
                                  assessments.map((item, passageIndex) => (
                                    <div
                                      className="passage-card"
                                      key={passageIndex}
                                    >
                                      <div className="passage-heading">
                                        <span>
                                          PAGE {item.page ?? "N/A"}
                                        </span>

                                        <span
                                          className={`verification-badge ${getVerificationClass(item.assessment?.status)}`}
                                        >
                                          {getVerificationLabel(
                                            item.assessment?.status
                                          )}
                                        </span>
                                      </div>

                                      <p>{item.passage}</p>

                                      {typeof item.assessment?.confidence === "number" && (
                                        <div className="confidence-row">
                                          <span>AI confidence</span>

                                          <strong>
                                            {(item.assessment.confidence * 100).toFixed(1)}%
                                          </strong>
                                        </div>
                                      )}
                                    </div>
                                  ))
                                ) : (
                                  <p className="verification-note">
                                    {evidence.message ||
                                      verification.message ||
                                      "No evidence passages were assessed."}
                                  </p>
                                )}
                              </div>

                            </div>
                          );
                        })
                      )}

                    </div>
                  );
                })
              )}

            </div>

            {/* REPORT CONCLUSION */}

            <div className="report-conclusion">

              <h2>Interpretation & Limitations</h2>

              <p>
                This report presents automated assessments of
                retrieved text passages against extracted research
                claims. The classifications are generated by an
                AI natural language inference model.
              </p>

              <p>
                A Supported result indicates that the retrieved
                passage is assessed as supporting the claim.
                A Contradicted result indicates an apparent
                contradiction. Insufficient Evidence means the
                available passage does not provide enough
                information for a confident assessment.
              </p>

              <p>
                Citation matching confirms bibliographic
                relationships, not scientific validity. AI
                predictions are not proof of scientific truth.
                Researchers should review original publications,
                methodology, context and source quality before
                drawing conclusions.
              </p>

              <div className="report-footer">
                Generated by CiteVerify AI · Research Trust &
                Evidence Intelligence Platform
              </div>

            </div>

            <div className="notice no-print">
              <AlertCircle size={17} />

              To save this report, select Download PDF and choose
              Save as PDF in the browser's print window.
            </div>

          </div>
        )}

      </section>
    );
  };

  // ==================================================
  // RESET
  // ==================================================

  const resetAnalyzer = () => {
    setFile(null);
    setResult(null);
    setResearchData(null);
    setEvidenceData(null);

    setError("");
    setResearchError("");
    setEvidenceError("");

    setActiveTab("claims");
    setActivePage("analyzer");
  };

  // ==================================================
  // MAIN APPLICATION
  // ==================================================

  return (
    <div className="app-shell">

      {/* SIDEBAR */}

      <aside className="sidebar">

        <div className="brand">
          <ShieldCheck size={27} />

          <span>
            CiteVerify <b>AI</b>
          </span>
        </div>

        <div className="side-label">
          WORKSPACE
        </div>

        <button
          className={`side-item ${
            activePage === "analyzer" ? "active" : ""
          }`}
          onClick={() => setActivePage("analyzer")}
        >
          <FileText size={18} />
          Document Analyzer
        </button>

        <button
          className={`side-item ${
            activePage === "research" ? "active" : ""
          }`}
          onClick={() => setActivePage("research")}
        >
          <Search size={18} />
          Research Finder
        </button>

        <button
          className={`side-item ${
            activePage === "evidence" ? "active" : ""
          }`}
          onClick={() => setActivePage("evidence")}
        >
          <BrainCircuit size={18} />
          Evidence Intelligence
        </button>

        <button
          className={`side-item ${
            activePage === "citations" ? "active" : ""
          }`}
          onClick={() => setActivePage("citations")}
        >
          <Quote size={18} />
          Citation Intelligence
        </button>

        <button
  className={`side-item ${
    activePage === "reports" ? "active" : ""
  }`}
  onClick={() => setActivePage("reports")}
>
  <FileCheck size={18} />
  Verification Reports
</button>

        <div className="sidebar-bottom">

          <div className="sidebar-status">
            <Activity size={16} />
            Research engine ready
          </div>

          <small>
            CiteVerify AI · Version 1.1
          </small>

        </div>

      </aside>

      {/* MAIN CONTENT */}

      <main className="main-content">

        <header className="topbar">

          <div>
            <span className="breadcrumb">
  WORKSPACE /{" "}
  {activePage === "analyzer"
    ? "DOCUMENT ANALYZER"
    : activePage === "research"
    ? "RESEARCH FINDER"
    : activePage === "citations"
    ? "CITATION INTELLIGENCE"
    : activePage === "reports"
    ? "VERIFICATION REPORTS"
    : "EVIDENCE INTELLIGENCE"}
</span>

            <h3>Research Intelligence</h3>
          </div>

          <div className="topbar-right">
            <span className="live-dot"></span>
            SYSTEM ONLINE
          </div>

        </header>

        <section className="content-area">

          {activePage === "reports" ? (
  renderReportPage()
) : activePage === "citations" ? (
  renderCitationPage()
) : activePage === "research" ? (
  renderResearchPage()
) : activePage === "evidence" ? (
  renderEvidencePage()
) : (

            <>

              <div className="page-heading">

                <div>
                  <span className="eyebrow">
                    <BrainCircuit size={15} />
                    AI-POWERED RESEARCH ANALYSIS
                  </span>

                  <h1>Document Analyzer</h1>

                  <p>
                    Discover claims, identify citations and prepare
                    your research for evidence verification.
                  </p>
                </div>

              </div>

              {/* UPLOAD CARD */}

              <div className="upload-card">

                <div className="section-title">

                  <div>
                    <h2>Upload Research Document</h2>

                    <p>
                      Start by submitting your academic research PDF.
                    </p>
                  </div>

                  <span className="secure-tag">
                    <ShieldCheck size={14} />
                    SECURE PROCESSING
                  </span>

                </div>

                <div
                  className={`drop-zone ${
                    dragging ? "dragging" : ""
                  }`}
                  onDragOver={(e) => {
                    e.preventDefault();
                    setDragging(true);
                  }}
                  onDragLeave={() => setDragging(false)}
                  onDrop={(e) => {
                    e.preventDefault();
                    setDragging(false);
                    selectFile(e.dataTransfer.files[0]);
                  }}
                >

                  {!file ? (

                    <>
                      <div className="upload-icon">
                        <UploadCloud size={34} />
                      </div>

                      <h3>
                        Drop your research PDF here
                      </h3>

                      <p>
                        or select a document from your computer
                      </p>

                      <label className="browse-button">
                        Browse Files

                        <input
                          type="file"
                          accept=".pdf,application/pdf"
                          hidden
                          onChange={(e) =>
                            selectFile(e.target.files[0])
                          }
                        />
                      </label>

                      <small>
                        PDF FORMAT · MAXIMUM 15 MB
                      </small>
                    </>

                  ) : (

                    <div className="selected-file">

                      <div className="file-icon">
                        <FileText size={30} />
                      </div>

                      <div className="file-details">
                        <h3>{file.name}</h3>

                        <p>
                          {(file.size / 1024 / 1024).toFixed(2)}
                          {" "}MB · PDF Document
                        </p>
                      </div>

                      <button
                        className="remove-button"
                        onClick={resetAnalyzer}
                        disabled={loading}
                      >
                        <X size={19} />
                      </button>

                    </div>

                  )}

                </div>

                {error && (
                  <div className="error-message">
                    <AlertCircle size={18} />
                    {error}
                  </div>
                )}

                <div className="upload-footer">

                  <span>
                    <ShieldCheck size={16} />
                    Original document is processed in memory.
                  </span>

                  <button
                    className="analyze-button"
                    onClick={analyzeDocument}
                    disabled={!file || loading}
                  >
                    {loading ? (
                      <>
                        <LoaderCircle className="spin" size={18} />
                        Analyzing Document...
                      </>
                    ) : (
                      <>
                        Analyze Document
                        <ArrowRight size={18} />
                      </>
                    )}
                  </button>

                </div>

              </div>

              {/* ANALYSIS RESULTS */}

              {result && (

                <section className="results-section">

                  <div className="results-heading">

                    <div>
                      <span className="eyebrow">
                        <CheckCircle2 size={15} />
                        EXTRACTION COMPLETED
                      </span>

                      <h2>Document Intelligence Report</h2>

                      <p>
                        {result.document?.name || file?.name}
                      </p>
                    </div>

                    <button
                      className="secondary-button"
                      onClick={resetAnalyzer}
                    >
                      New Analysis
                    </button>

                  </div>

                  {/* DASHBOARD STATISTICS */}

                  <div className="stats-grid">

                    <div className="stat-card">
                      <FileText />
                      <span>Total Pages</span>
                      <h2>{result.document?.pages ?? 0}</h2>
                    </div>

                    <div className="stat-card">
                      <BrainCircuit />
                      <span>Potential Claims</span>
                      <h2>
                        {result.analysis?.total_claims ?? 0}
                      </h2>
                    </div>

                    <div className="stat-card">
                      <Quote />
                      <span>Citations Found</span>
                      <h2>
                        {result.analysis?.total_citations ?? 0}
                      </h2>
                    </div>

                    <div className="stat-card">
                      <FileCheck />
                      <span>References Found</span>
                      <h2>
                        {getReferenceCount(result)}
                      </h2>
                    </div>

                    <div className="stat-card">
                      <Activity />
                      <span>Word Count</span>
                      <h2>
                        {(result.document?.word_count ?? 0).toLocaleString()}
                      </h2>
                    </div>

                  </div>

                  <div className="results-card">

                    <div className="result-tabs">

                      <button
                        className={
                          activeTab === "claims"
                            ? "tab active-tab"
                            : "tab"
                        }
                        onClick={() => setActiveTab("claims")}
                      >
                        Extracted Claims
                      </button>

                      <button
                        className={
                          activeTab === "citations"
                            ? "tab active-tab"
                            : "tab"
                        }
                        onClick={() => setActiveTab("citations")}
                      >
                        Citations
                      </button>

                      <button
                        className={
                          activeTab === "references"
                            ? "tab active-tab"
                            : "tab"
                        }
                        onClick={() => setActiveTab("references")}
                      >
                        References ({getReferenceCount(result)})
                      </button>

                      <button
                        className={
                          activeTab === "preview"
                            ? "tab active-tab"
                            : "tab"
                        }
                        onClick={() => setActiveTab("preview")}
                      >
                        Text Preview
                      </button>

                    </div>

                    <div className="result-body">

                      {/* CLAIMS */}

                      {activeTab === "claims" && (

                        result.claims.length > 0 ? (

                          result.claims.map((item, index) => (

                            <div
                              className="claim-item"
                              key={item.id ?? index}
                            >

                              <div className="claim-number">
                                {String(
                                  item.id ?? index + 1
                                ).padStart(2, "0")}
                              </div>

                              <div>
                                <span className="claim-label">
                                  POTENTIAL RESEARCH CLAIM
                                </span>

                                <p>
                                  {item.claim || item.text}
                                </p>
                              </div>

                            </div>

                          ))

                        ) : (
                          <p className="empty-state">
                            No potential claims were detected.
                          </p>
                        )

                      )}

                      {/* CITATIONS */}

                      {activeTab === "citations" && (

                        result.citations.length > 0 ? (

                          result.citations.map((citation, index) => (

                            <div
                              className="citation-item"
                              key={index}
                            >
                              <Quote size={18} />

                              <span>
                                {typeof citation === "string"
                                  ? citation
                                  : JSON.stringify(citation)}
                              </span>
                            </div>

                          ))

                        ) : (
                          <p className="empty-state">
                            No supported citation patterns were detected.
                          </p>
                        )

                      )}

                      {/* REFERENCES */}

                      {activeTab === "references" && (

                        normalizeReferences(result).length > 0 ? (

                          normalizeReferences(result).map(
                            (reference, index) => (

                              <div
                                className="citation-item"
                                key={index}
                              >
                                <FileCheck size={18} />

                                <span>
                                  {getReferenceText(reference)}
                                </span>
                              </div>

                            )
                          )

                        ) : (
                          <p className="empty-state">
                            No reference entries were extracted.
                          </p>
                        )

                      )}

                      {/* TEXT PREVIEW */}

                      {activeTab === "preview" && (
                        <pre className="text-preview">
                          {result.preview}
                        </pre>
                      )}

                    </div>

                  </div>

                  <div className="notice">
                    <AlertCircle size={17} />

                    These are preliminary extraction results,
                    not verified scientific findings. Use Research
                    Finder and Evidence Intelligence for further analysis.
                  </div>

                  <button
                    className="analyze-button research-launch"
                    onClick={() => setActivePage("research")}
                  >
                    Find Research Publications
                    <ArrowRight size={18} />
                  </button>

                  <button
                    className="analyze-button evidence-launch"
                    onClick={analyzeEvidence}
                    disabled={evidenceLoading}
                  >
                    {evidenceLoading ? (
                      <>
                        <LoaderCircle className="spin" size={18} />
                        Verifying Evidence...
                      </>
                    ) : (
                      <>
                        <BrainCircuit size={18} />
                        Run AI Evidence Verification
                        <ArrowRight size={18} />
                      </>
                    )}
                  </button>

                  {evidenceError && (
                    <div className="error-message">
                      <AlertCircle size={18} />
                      {evidenceError}
                    </div>
                  )}

                </section>

              )}

            </>

          )}

        </section>

      </main>

    </div>
  );
}

export default App;
