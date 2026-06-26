"""Classify a job email into {company, role, status, source} with regex only.

No external API calls, no AI billing -> 100% free. Status vocabulary
(priority order used for de-dup in ingest.py):
  Offer > Interview > Rejected > Withdrawn > Viewed > Awaiting > Unknown
"""
import re

STATUS_PRIORITY = {
    "Unknown": 0, "Awaiting": 1, "Viewed": 2, "Withdrawn": 3,
    "Rejected": 4, "Interview": 5, "Offer": 6,
}

_STATUS_RULES = [
    ("Offer", r"pleased to offer|offer of employment|formal offer|we'?d like to offer you|"
              r"we are delighted to offer|congratulations.*offer|offer letter|"
              r"job offer|employment offer|extend.*offer"),
    ("Rejected", r"regret to inform|unfortunately|not been (successful|selected)|"
                 r"not successful|decided not to (proceed|move ahead)|not to progress|"
                 r"other candidate|unsuccessful (on this occasion|in this|at this)|"
                 r"will not be progressing|decided to (move ahead|choose another)|"
                 r"only contact(ing)? .{0,30}shortlist|not the right fit|"
                 r"moving forward with other|we have decided to move forward|"
                 r"we will not be moving forward"),
    ("Withdrawn", r"position (has been )?(closed|withdrawn|filled)|no longer (available|recruiting)|"
                  r"role (has been )?closed|ending the search|role has been filled|"
                  r"hiring process has concluded"),
    ("Interview", r"\binterview\b|phone (chat|screen|call|interview)|"
                  r"schedule a (call|time|chat)|book a time|are you available|"
                  r"would (love|like) to (have a|chat|speak|invite)|set up a time|next round|"
                  r"invitation to interview|interview invitation|let.?s schedule|"
                  r"move to the next stage|moving you forward|advance to the next round|"
                  r"we'd like to invite|please join us for"),
    ("Viewed", r"your application was viewed|viewed by|profile viewed"),
    ("Awaiting", r"thank you for applying|thanks for applying|received your application|"
                 r"application (was )?(sent|submitted|received)|acknowledge receipt|"
                 r"we have received|application confirmed|application successfully submitted"),
]

_SOURCE_RULES = [
    ("LinkedIn", r"linkedin\.com|your application was sent to|via linkedin|"
                 r"linkedincareers|from linkedin|on linkedin"),
    ("Indeed", r"indeed\.com|your application to .+ at |from indeed|via indeed|"
              r"indeedemail|on indeed"),
    ("Seek", r"seek\.com|seek\.com\.au|seek\.co\.nz|hays\.com|employment hero|"
             r"from seek|via seek|seek\.asia"),
    ("Glassdoor", r"glassdoor\.com|from glassdoor|via glassdoor"),
    ("ZipRecruiter", r"ziprecruiter\.com|from ziprecruiter|via ziprecruiter"),
    ("AngelList", r"angellist\.com|angel\.co|from angellist|via angellist|"
                  r"wellfound\.com"),
    ("Workable", r"workable\.com|from workable|via workable|apply on workable"),
    ("Lever", r"lever\.co|lever-hosted.appspot.com|from lever|via lever"),
    ("Greenhouse", r"greenhouse\.io|from greenhouse|via greenhouse"),
    ("Talentdesk", r"talentdesk|from talentdesk|via talentdesk"),
    ("Twitter/X Jobs", r"twitter\.com.*jobs|x\.com.*jobs|from twitter|via twitter"),
    ("GitHub Jobs", r"github\.com.*jobs|from github|via github"),
    ("Stack Overflow", r"stackoverflow\.com|from stackoverflow|via stackoverflow"),
    ("Company", r""),
]


def _match(text, rules, default):
    for label, pattern in rules:
        if re.search(pattern, text, re.I):
            return label
    return default


def _guess_company(sender, subject, snippet):
    """Extract ONLY the company name from email sender domain."""

    # FIRST: Try to extract from sender email domain (most reliable)
    dom_match = re.search(r"@([\w.\-]+\.\w+)", sender)
    if dom_match:
        domain = dom_match.group(1).lower()

        # Extract base domain name
        parts = domain.split(".")
        company_from_domain = parts[-2] if len(parts) >= 2 else parts[0]
        company_from_domain = company_from_domain.title()

        # FILTER: Skip job boards and generic providers
        skip_domains = {
            "linkedin", "indeed", "seek", "glassdoor", "ziprecruiter", "angel",
            "workable", "lever", "greenhouse", "talentdesk", "twitter", "github",
            "stackoverflow", "gmail", "outlook", "yahoo", "hotmail", "aol",
            "mail", "noreply", "no-reply", "notifications", "mailer", "donotreply",
            "alert", "notification", "careers", "jobs", "recruit", "hr", "apply"
        }

        if company_from_domain.lower() not in skip_domains and len(company_from_domain) <= 50:
            return company_from_domain

    # SECOND: Extract from sender display name if it looks professional
    sender_name = re.sub(r"<.*?>", "", sender).strip().strip('"')
    if sender_name and "@" not in sender_name and 3 <= len(sender_name) <= 60:
        # Must look like a company name: has capital letters, no generic words
        if re.search(r"^[A-Z]", sender_name):
            # Filter noise
            if not re.search(r"\b(job|alert|notification|noreply|team|recruiting|careers|learning)\b", sender_name, re.I):
                return sender_name

    # THIRD: Last resort - extract from email start if it matches "CompanyName. We..."
    if re.match(r"^[A-Z][a-z\s\-&.]{2,40}\.\s+(?:We|Your|Dear|Thank|Hi|This)", snippet):
        match = re.match(r"^([A-Z][a-z\s\-&.]{2,40})\.", snippet)
        if match:
            return match.group(1).strip()

    return "Unknown"


def _guess_role(subject, snippet):
    """Extract job role from email content."""
    text = f"{subject}\n{snippet}".lower()

    # Look for role/position/job title mentions
    role_patterns = [
        r"(?:role|position|job|title|title:)\s*[:\-]?\s*([a-z\s\-/&.()]{3,80}?)(?:\s+(?:at|with|in|for|—)|\.|,|$|\n)",
        r"(?:applying for|application for|applying to)\s+(?:the\s+)?(?:role of\s+)?([a-z\s\-/&.()]{3,80}?)(?:\s+(?:at|with|in)|\.|,|$)",
        r"([a-z\s\-/&.()]{5,80}?)\s+(?:position|role|opportunity)(?:\s+at|\.|,|$)",
        r"(?:cloud|senior|junior|lead|staff|junior|support|engineer|analyst|manager|developer|technician|officer|specialist|architect|consultant|coordinator|administrator|technologist|operator|agent|associate|assistant|support|lead|officer|supervisor|director)\s+([a-z\s\-/&.()]{2,50}?)(?:\s+at|,|\.|$)",
    ]

    for pattern in role_patterns:
        match = re.search(pattern, text, re.I)
        if match:
            role = match.group(1).strip().title()
            # Validate: not too short, not garbage
            if 3 <= len(role) <= 90:
                # Filter noise
                if not re.search(r"^(your|the|a|an|and|or|for|with|at|in|we|thank|dear|hi|hello)", role, re.I):
                    return role

    return "Unknown"


def classify_with_rules(sender, subject, snippet):
    text = f"{subject}\n{snippet}"
    return {
        "company": _guess_company(sender, subject, snippet),
        "role": _guess_role(subject, snippet),
        "status": _match(text, _STATUS_RULES, "Unknown"),
        "source": _match(f"{sender} {text}", _SOURCE_RULES, "Company"),
    }
