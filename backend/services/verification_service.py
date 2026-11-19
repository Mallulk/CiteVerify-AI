
import torch

from transformers import (
    AutoTokenizer,
    AutoModelForSequenceClassification
)


MODEL_NAME = "cross-encoder/nli-deberta-v3-small"

tokenizer = None
model = None


def load_model():
    """
    Load the NLI model only once.
    """

    global tokenizer, model

    if tokenizer is None or model is None:

        print("Loading CiteVerify AI NLI model...")

        tokenizer = AutoTokenizer.from_pretrained(MODEL_NAME)

        model = AutoModelForSequenceClassification.from_pretrained(
            MODEL_NAME
        )

        model.eval()

        print("NLI model loaded successfully.")


def classify_passage(claim, passage):
    """
    Compare a research passage (premise)
    against a research claim (hypothesis).
    """

    load_model()

    inputs = tokenizer(
        passage,
        claim,
        return_tensors="pt",
        truncation=True,
        max_length=512
    )

    with torch.no_grad():

        outputs = model(**inputs)

        probabilities = torch.softmax(
            outputs.logits,
            dim=1
        )[0]

    labels = model.config.id2label

    scores = {}

    for index, probability in enumerate(probabilities):

        label = str(labels[index]).lower()

        if "entail" in label:
            scores["entailment"] = float(probability)

        elif "contrad" in label:
            scores["contradiction"] = float(probability)

        elif "neutral" in label:
            scores["neutral"] = float(probability)

    # Handle unexpected model label formats safely.
    if len(scores) != 3:

        return {
            "success": False,
            "status": "needs_manual_review",
            "error": "Unexpected NLI model labels",
            "model_labels": {
                str(key): str(value)
                for key, value in labels.items()
            }
        }

    ordered_scores = sorted(
        scores.values(),
        reverse=True
    )

    confidence = ordered_scores[0]

    margin = ordered_scores[0] - ordered_scores[1]

    if confidence < 0.65 or margin < 0.10:

        status = "needs_manual_review"

    elif scores["entailment"] == confidence:

        status = "supported"

    elif scores["contradiction"] == confidence:

        status = "contradicted"

    else:

        status = "insufficient_evidence"

    return {
        "success": True,
        "status": status,
        "confidence": round(confidence, 4),
        "scores": {
            key: round(value, 4)
            for key, value in scores.items()
        },
        "model": MODEL_NAME
    }


def verify_claim_against_passages(claim, passages):
    """
    Assess each passage and produce an overall
    evidence assessment.

    Conflicting passage results require manual review.
    """

    if not isinstance(passages, list) or not passages:

        return {
            "success": True,
            "status": "insufficient_evidence",
            "total_passages": 0,
            "assessments": [],
            "message": "No evidence passages were supplied."
        }

    assessments = []

    for item in passages:

        if not isinstance(item, dict):
            continue

        passage = item.get("passage", "")

        if not isinstance(passage, str) or not passage.strip():
            continue

        result = classify_passage(
            claim,
            passage
        )

        assessments.append({
            "page": item.get("page"),
            "passage": passage,
            "relevance_score": item.get("relevance_score"),
            "assessment": result
        })

    successful = [
        item["assessment"]["status"]
        for item in assessments
        if item["assessment"].get("success")
    ]

    supported = successful.count("supported")
    contradicted = successful.count("contradicted")

    if not successful:

        overall_status = "needs_manual_review"

    elif supported and contradicted:

        overall_status = "needs_manual_review"

    elif supported:

        overall_status = "supported"

    elif contradicted:

        overall_status = "contradicted"

    elif "needs_manual_review" in successful:

        overall_status = "needs_manual_review"

    else:

        overall_status = "insufficient_evidence"

    return {
        "success": True,
        "status": overall_status,
        "total_passages": len(assessments),
        "supported_passages": supported,
        "contradicted_passages": contradicted,
        "assessments": assessments,
        "message": (
            "NLI model assessment completed. "
            "Results require human review before being treated "
            "as scientific conclusions."
        )
    }
