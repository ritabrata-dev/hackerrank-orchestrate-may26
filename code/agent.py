from retriever import clean_text, retrieve

ESCALATION_KEYWORDS = [
    "fraud",
    "unauthorized",
    "hacked",
    "stolen",
    "legal",
    "police",
    "chargeback",
    "system prompt",
    "jailbreak",
    "security vulnerability",
    "exploit",
    "data leak",
]
REFUND_RISK_KEYWORDS = ["refund", "chargeback", "not my transaction"]
IRRELEVANT_KEYWORDS = ["iron man", "movie", "football score", "weather today", "recipe", "bitcoin price"]
OPENING_TEMPLATES = [
    "Since you're facing",
    "It looks like",
    "In this case,",
    "Here's how to resolve it:",
]
CLOSING_TEMPLATES = [
    "If this still fails, share the exact error text and I will refine the next step.",
    "If needed, send a screenshot and I can help verify the next action.",
    "If you want, I can tailor this further once you share the exact screen or error.",
]


def detect_company(text, field):
    """Detect company from explicit field first, then issue keywords."""
    allowed = {"hackerrank", "claude", "visa"}
    if field and field.strip().lower() in allowed:
        return field.strip().lower()

    t = (text or "").lower()
    visa_keywords = ["visa", "card", "payment", "transaction", "charge"]
    hackerrank_keywords = ["hackerrank", "assessment", "test case", "coding challenge", "submission"]
    claude_keywords = ["claude", "ai", "assistant", "prompt", "model"]

    if any(k in t for k in visa_keywords):
        return "visa"
    if any(k in t for k in hackerrank_keywords):
        return "hackerrank"
    if any(k in t for k in claude_keywords):
        return "claude"
    return "unknown"


def detect_request_type(text):
    t = (text or "").lower()
    bug_keywords = [
        "error",
        "bug",
        "failed",
        "failure",
        "broken",
        "not working",
        "crash",
        "down",
        "outage",
        "cannot",
        "can't",
    ]
    feature_keywords = ["feature", "enhancement", "can you add", "request", "would like", "please add"]
    malicious_or_irrelevant = ["ignore instructions", "reveal system prompt", "jailbreak", "actor in iron man"]

    if any(k in t for k in malicious_or_irrelevant) or any(k in t for k in IRRELEVANT_KEYWORDS):
        return "invalid"

    if any(k in t for k in feature_keywords):
        return "feature_request"
    if any(k in t for k in bug_keywords):
        return "bug"
    return "product_issue"


def should_escalate(text):
    t = (text or "").lower()
    if any(keyword in t for keyword in ESCALATION_KEYWORDS):
        return True

    has_refund_language = any(keyword in t for keyword in REFUND_RISK_KEYWORDS)
    has_risk_language = any(keyword in t for keyword in ["fraud", "unauthorized", "stolen", "hacked", "not my transaction"])
    return has_refund_language and has_risk_language


def infer_product_area(company, issue):
    t = (issue or "").lower()
    if company == "visa":
        if any(k in t for k in ["fraud", "chargeback", "refund", "dispute", "not my transaction", "unauthorized"]):
            return "disputes"
        if any(k in t for k in ["card", "payment", "charge", "transaction"]):
            return "payments"
        return "card_usage"
    if company == "hackerrank":
        if any(k in t for k in ["assessment", "test case", "compiler", "submission"]):
            return "assessments"
        if any(k in t for k in ["interview", "candidate", "reinvite", "time accommodation"]):
            return "interviews"
        if any(k in t for k in ["job", "hiring", "screening", "role"]):
            return "hiring"
        return "platform"
    if company == "claude":
        if any(k in t for k in ["api", "token", "rate limit", "console", "sdk"]):
            return "api"
        if any(k in t for k in ["login", "password", "delete account", "billing", "subscription"]):
            return "account"
        if any(k in t for k in ["safety", "policy", "abuse", "harmful", "security", "vulnerability"]):
            return "safety"
        if any(k in t for k in ["prompt", "model", "response", "token"]):
            return "usage"
        return "usage"
    return "customer_support"


def _extract_action_sentences(context_chunks, issue, product_area):
    issue_words = {w for w in clean_text(issue).split() if len(w) >= 5}
    area_keywords = {
        "assessments": {"assessment", "candidate", "invite", "test", "time"},
        "interviews": {"interview", "candidate", "schedule", "invite"},
        "hiring": {"role", "hiring", "test", "question"},
        "platform": {"test", "settings", "candidate", "invite", "account"},
        "payments": {"card", "payment", "transaction", "visa"},
        "disputes": {"fraud", "chargeback", "dispute", "unauthorized"},
        "card_usage": {"card", "visa", "lost", "stolen"},
        "usage": {"conversation", "chat", "share", "delete", "privacy"},
        "account": {"account", "password", "login", "delete"},
        "api": {"api", "token", "console", "request"},
    }
    relevant_terms = area_keywords.get(product_area, set())
    sentences = []
    for chunk in context_chunks[:3]:
        for raw_sentence in chunk.replace("\n", " ").split(". "):
            sentence = raw_sentence.strip().strip(".")
            if len(sentence) < 25:
                continue
            if any(
                cue in sentence.lower()
                for cue in [
                    "go to",
                    "click",
                    "select",
                    "set",
                    "update",
                    "contact",
                    "report",
                    "log in",
                    "reset",
                    "delete",
                    "reinvite",
                    "add time",
                    "call",
                ]
            ):
                concise = sentence.strip()
                if len(concise) > 220:
                    concise = concise[:220].rsplit(" ", 1)[0].strip()
                concise = concise.rstrip(".") + "."
                if len(concise) < 45 or concise.endswith(" your.") or concise.endswith(" the."):
                    continue
                if any(bad in concise.lower() for bad in ["â", "✅", "feature ashby", "thumbs down button"]):
                    continue
                sentence_words = {w for w in clean_text(concise).split() if len(w) >= 5}
                if issue_words and len(issue_words & sentence_words) == 0:
                    continue
                if relevant_terms and len(relevant_terms & sentence_words) == 0:
                    continue
                if concise.lower() not in [s.lower() for s in sentences]:
                    sentences.append(concise)
            if len(sentences) == 3:
                return sentences
    return sentences


def _pick_variant(text, variants):
    if not variants:
        return ""
    seed = sum(ord(c) for c in (text or ""))
    return variants[seed % len(variants)]


def _issue_focus(issue):
    cleaned = clean_text(issue or "")
    if not cleaned:
        return "your request"
    words = cleaned.split()[:9]
    return " ".join(words)


def _issue_phrase(issue):
    t = (issue or "").lower()
    if "site is down" in t or "outage" in t or "none of the pages" in t:
        return "the platform appears to be unavailable"
    if "extra time" in t or "reinvite" in t:
        return "a request to re-invite a candidate with extra time"
    if "delete" in t and "account" in t:
        return "an account deletion request"
    if any(k in t for k in ["stolen", "unauthorized", "not my transaction", "fraud"]):
        return "a potentially unauthorized transaction"
    return _issue_focus(issue)


def build_opening_line(issue, product_area):
    t = (issue or "").lower()
    opening = _pick_variant(issue, OPENING_TEMPLATES)
    phrase = _issue_phrase(issue)

    if "extra time" in t or "reinvite" in t:
        detail = "you can resolve it by updating assessment timing and sending a fresh invite."
    elif "delete" in t and "account" in t:
        detail = "you can complete it by setting a password first and then deleting the account."
    elif any(k in t for k in ["stolen", "unauthorized", "fraud", "not my transaction"]):
        detail = "this should be handled through the secure dispute process."
    elif product_area == "api":
        detail = "the next step is to verify API or console configuration."
    elif product_area in {"assessments", "interviews", "hiring", "platform"}:
        detail = "you can usually resolve this from the relevant HackerRank settings."
    elif product_area in {"payments", "disputes", "card_usage"}:
        detail = "this follows standard Visa support steps."
    elif product_area in {"usage", "account", "safety"}:
        detail = "Claude support steps should resolve it."
    else:
        detail = "there is a support-driven path to resolve it."

    if opening == "Here's how to resolve it:":
        return f"{opening} {detail[0].upper()}{detail[1:]}"
    if opening == "Since you're facing":
        return f"{opening} {phrase}, {detail}"
    return f"{opening} {phrase}, {detail}"


def _issue_specific_steps(issue, product_area):
    t = (issue or "").lower()
    if any(k in t for k in ["security vulnerability", "exploit", "data leak"]):
        return [
            "Stop any testing or sharing that could increase impact.",
            "Capture evidence (timestamps, request IDs, screenshots, affected endpoints).",
            "Share those details with security support for immediate investigation.",
        ]

    # Visa-specific actions
    if product_area == "disputes":
        if any(k in t for k in ["fraud", "unauthorized", "not my transaction", "stolen"]):
            return [
                "Immediately contact your card issuer and request a card block/replacement.",
                "Report the unauthorized transaction and ask the issuer to open a fraud dispute.",
                "Provide transaction details (date, amount, merchant) and keep the case reference number.",
            ]
        return [
            "Contact your issuing bank and raise a charge dispute for the transaction.",
            "Share transaction details (amount, date, merchant, and any proof of cancellation/return).",
            "Track the dispute status with your bank until chargeback resolution is complete.",
        ]
    if product_area == "payments":
        return [
            "Confirm the card number, expiry, CVV, and billing address are entered correctly.",
            "Retry the payment once and check whether your bank declined the transaction.",
            "If it still fails, contact your issuer to allow/verify the transaction attempt.",
        ]

    # HackerRank-specific actions
    if product_area in {"assessments", "interviews"} and any(k in t for k in ["recruiter", "result", "rejected", "reschedule", "submission", "assessment"]):
        return [
            "Contact the recruiter/hiring coordinator with your test link and completion timestamp.",
            "Ask them to verify submission status in their HackerRank dashboard.",
            "If needed, request a re-invite or retry window from the recruiter/support team.",
        ]
    if product_area in {"assessments", "interviews", "hiring"}:
        return [
            "Confirm the test/interview link, schedule, and candidate details in your dashboard.",
            "Retry the flow once from a clean browser session to rule out local issues.",
            "If the issue remains, share the test/interview ID with support for investigation.",
        ]
    if product_area in {"platform", "hiring"} and any(k in t for k in ["down", "bug", "error", "not working", "outage", "blocked"]):
        return [
            "Retry in an incognito window or another browser to rule out local cache issues.",
            "Capture the exact error and timestamp, then report it to HackerRank support.",
            "Share affected test/interview IDs so support can investigate faster.",
        ]
    if product_area == "platform":
        return [
            "Reproduce the issue once and note the exact page, action, and timestamp.",
            "Try again from a clean browser session (incognito or another browser).",
            "Submit the error details to support with any relevant IDs or screenshots.",
        ]

    # Claude-specific actions
    if product_area in {"api", "usage"}:
        return [
            "Check account settings and usage/rate limits for the workspace or API key.",
            "Verify the request configuration (model, key, organization/workspace, and permissions).",
            "Retry with a minimal request and share the exact error if it still fails.",
        ]
    if product_area == "safety":
        return [
            "Avoid sharing additional sensitive content in the same thread.",
            "Collect evidence (prompt, response, and timestamp) for the safety/security team.",
            "Submit the report through official security channels for immediate review.",
        ]

    if "extra time" in t or "reinvite" in t:
        return [
            "Open the test in HackerRank and go to the candidate list.",
            "Select the candidate and apply time accommodation before re-inviting.",
            "Re-send the invite and confirm the updated duration in candidate settings.",
        ]
    if "delete" in t and "account" in t:
        return [
            "Reset or set a password for the account if it was created with Google/social login.",
            "Sign in, open account settings, and choose Delete Account.",
            "Confirm deletion with the password prompt to complete the request.",
        ]
    if "site is down" in t or "outage" in t or "none of the pages" in t:
        return [
            "Check the service status page first to confirm whether this is a platform-wide outage.",
            "Capture the exact error page and timestamp, then retry in a private/incognito window.",
            "If it persists, share the outage evidence with support so they can escalate quickly.",
        ]
    if product_area == "usage" and any(k in t for k in ["conversation", "private", "delete"]):
        return [
            "Open the conversation and use the chat options menu to delete it.",
            "If needed, disable sharing and remove any public links to that chat.",
            "Review account privacy settings to prevent future accidental retention.",
        ]
    return []


def _is_actionable_step(step):
    low = step.lower()
    action_cues = [
        "contact",
        "report",
        "open",
        "go to",
        "select",
        "click",
        "check",
        "verify",
        "retry",
        "reset",
        "delete",
        "request",
        "share",
        "confirm",
        "submit",
        "ask",
        "provide",
        "capture",
        "track",
    ]
    return any(cue in low for cue in action_cues)


def _build_closing(issue, request_type, confidence):
    if request_type in {"feature_request", "invalid"}:
        return ""
    if confidence == "high":
        return ""
    return _pick_variant(issue + request_type + confidence, CLOSING_TEMPLATES)


def _estimate_retrieval_confidence(issue, context_chunks):
    if not context_chunks:
        return "none"
    q_words = set(clean_text(issue).split())
    c_words = set(clean_text(" ".join(context_chunks)).split())
    overlap = len(q_words & c_words)
    if len(context_chunks) >= 2 and overlap >= 8:
        return "high"
    if overlap >= 4:
        return "medium"
    return "low"


def _escalation_reasons(issue):
    t = (issue or "").lower()
    reasons = []
    if any(k in t for k in ["fraud", "unauthorized", "not my transaction", "chargeback", "refund"]):
        reasons.append("possible fraudulent or unauthorized transaction")
    if any(k in t for k in ["hacked", "account compromise", "stolen"]):
        reasons.append("possible account compromise")
    if any(k in t for k in ["legal", "police"]):
        reasons.append("legal or law-enforcement involvement")
    if any(k in t for k in ["system prompt", "jailbreak", "ignore instructions", "prompt injection"]):
        reasons.append("prompt-injection or security manipulation attempt")
    if any(k in t for k in ["security vulnerability", "exploit", "data leak"]):
        reasons.append("reported security vulnerability or potential data leak")
    return reasons


def _confidence_from_score(score):
    if score >= 3:
        return "high"
    if score >= 1:
        return "medium"
    return "low"


def _split_context_sentences(context):
    if not context:
        return []
    cleaned = context.replace("\n", " ")
    parts = [s.strip() for s in cleaned.split(". ")]
    sentences = []
    for part in parts:
        line = part.strip().rstrip(".")
        if len(line) < 35:
            continue
        if any(bad in line.lower() for bad in ["title_slug", "source_url", "article_slug", "final url", "last modified", "<", ">"]):
            continue
        sentences.append(line + ".")
    return sentences


def _first_issue_line(issue, product_area, cautious=False):
    opening = _pick_variant(issue, OPENING_TEMPLATES)
    focus = _issue_phrase(issue)
    if cautious:
        return f"{opening} {focus}, this may help based on similar support cases in {product_area.replace('_', ' ')}."
    return f"{opening} {focus}, here are the most relevant support steps."


def build_confidence_response(issue, context, product_area, score):
    confidence = _confidence_from_score(score)
    cautious = score < 3
    sentences = _split_context_sentences(context)
    steps = _issue_specific_steps(issue, product_area)

    if not steps:
        action_sentences = _extract_action_sentences([context], issue, product_area)
        steps = action_sentences[:3]

    if not steps and sentences:
        steps = sentences[:2]

    steps = [s for s in steps if _is_actionable_step(s)]
    if not steps:
        steps = _issue_specific_steps(issue, product_area)

    if not steps:
        return ""

    lines = [_first_issue_line(issue, product_area, cautious=cautious), "", "Steps:"]
    for idx, step in enumerate(steps[:3], start=1):
        lines.append(f"{idx}. {step}")

    if cautious:
        lines.append("")
        lines.append("If these steps do not match what you see on-screen, share the exact error and I will narrow this further.")

    response = "\n".join(lines).strip()
    if len(response) > 900:
        response = response[:900].rsplit(" ", 1)[0] + "..."
    return response


def process_ticket(issue, company):
    comp = detect_company(issue, company)
    request_type = detect_request_type(issue)
    product_area = infer_product_area(comp, issue)
    retrieval_company = comp if comp in {"visa", "hackerrank", "claude"} else None
    issue_lower = (issue or "").strip().lower()

    if issue_lower in {"thanks", "thank you", "thank you for helping me", "thank you for your help"}:
        return {
            "status": "replied",
            "product_area": product_area,
            "request_type": "product_issue",
            "response": "You are welcome. If you need help with another support issue, share the details and I can assist right away.",
            "justification": "Replied directly because this is a conversational acknowledgement and not a support problem requiring retrieval or escalation.",
        }

    if request_type == "invalid" and not should_escalate(issue):
        return {
            "status": "replied",
            "product_area": product_area,
            "request_type": "invalid",
            "response": "I can only help with Visa, HackerRank, or Claude support topics. Please share a support-related issue and I will assist right away.",
            "justification": "Marked as invalid because the query appears irrelevant or malicious; no high-risk escalation indicators found.",
        }

    if should_escalate(issue):
        reasons = _escalation_reasons(issue)
        reason_text = "; ".join(reasons) if reasons else "high-risk security indicators"
        return {
            "status": "escalated",
            "product_area": "security",
            "request_type": "product_issue" if request_type == "invalid" else request_type,
            "response": f"We are escalating this ticket to a specialist because it indicates {reason_text}. A human security/support team member should review and take the next action.",
            "justification": f"Escalated after detecting high-risk indicators: {reason_text}.",
        }

    context, score = retrieve(issue, retrieval_company)
    confidence = _confidence_from_score(score)

    if score >= 3:
        grounded_response = build_confidence_response(issue, context, product_area, score)
        if grounded_response:
            return {
                "status": "replied",
                "product_area": product_area,
                "request_type": request_type,
                "response": grounded_response,
                "justification": (
                    f"Classified as {request_type}; high confidence match from support corpus (score={score}); no escalation needed."
                ),
            }

    if score >= 1:
        cautious_response = build_confidence_response(issue, context, product_area, score)
        if cautious_response:
            return {
                "status": "replied",
                "product_area": product_area,
                "request_type": request_type,
                "response": cautious_response,
                "justification": (
                    f"Classified as {request_type}; medium confidence keyword match from support corpus (score={score}); replied cautiously without escalation."
                ),
            }

    if score == 0:
        return {
            "status": "replied",
            "product_area": product_area,
            "request_type": request_type,
            "response": (
                "I could not find a direct match for this exact issue in the current support corpus.\n\n"
                "Please share:\n"
                "1. The exact error message\n"
                "2. The steps you followed before the issue appeared\n"
                "3. A screenshot or timestamp\n\n"
                "With that, I can give a precise next action."
            ),
            "justification": (
                f"Classified as {request_type}; low confidence retrieval (score=0) with no direct corpus match; no escalation indicators detected."
            ),
        }

    return {
        "status": "replied",
        "product_area": product_area,
        "request_type": request_type,
        "response": "Please share the exact error text and what happened before this issue so I can provide the right next step.",
        "justification": f"Classified as {request_type}; retrieval confidence {confidence}; response returned without escalation.",
    }