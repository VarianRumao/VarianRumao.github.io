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
    """Extract company name - NOT job board platform."""
    text = f"{sender} {subject} {snippet}"

    # Priority 1: Explicit company mentions in common patterns
    patterns = [
        r"(?:application was sent to|application to|job at|position at)\s+([A-Za-z][A-Za-z0-9\s&.\-'()]+?)(?:\s+(?:for|in|role|position|department)|$)",
        r"Dear\s+([A-Za-z][A-Za-z0-9\s&.\-'()]+?)(?:\s+(?:team|hr|hiring))?[,:]",
        r"(?:company|employer):\s*([A-Za-z][A-Za-z0-9\s&.\-'()]+?)(?:\n|$)",
        r"(?:thank you|congratulations|regarding your application to)\s+([A-Za-z][A-Za-z0-9\s&.\-'()]+?)(?:\s+for|\s+position|$)",
    ]

    for pat in patterns:
        m = re.search(pat, text, re.I)
        if m:
            company = m.group(1).strip()
            company = re.sub(r"\s+(for|in|recruiting|careers|jobs|position|role).*$", "", company, flags=re.I).strip()
            if company and len(company) > 1 and len(company) < 80:
                return company

    # Priority 2: Extract from sender name (not domain)
    name = re.sub(r"<.*?>", "", sender).strip().strip('"')
    if name and "@" not in name and "noreply" not in name.lower() and len(name) > 2:
        # Clean "careers", "jobs", "recruiting" from sender name
        if not re.search(r"\b(careers|jobs|recruiting|applicant|notification)\b", name, re.I):
            return name

    # Priority 3: Extract domain but exclude job boards
    dom = re.search(r"@([\w.\-]+)", sender)
    if dom:
        domain = dom.group(1).split(".")[0].title()
        job_boards = ["linkedin", "indeed", "seek", "glassdoor", "ziprecruiter",
                     "angel", "workable", "lever", "greenhouse", "talent", "mail", "noreply"]
        if domain.lower() not in ["gmail", "outlook", "yahoo", "hotmail", "aol", "email"] and \
           domain.lower() not in job_boards:
            return domain

    return "Unknown"


def _guess_role(subject, snippet):
    """Extract job role/position title."""
    text = f"{subject} {snippet}"

    # More lenient patterns that don't require specific capitalization
    patterns = [
        r"(?:applying for|applied for|apply for|application for)\s+(?:the\s+)?(?:role|position|job|title)?s?\s*[:\"]?([^,.\n]{5,100}?)(?:[,.\n\)]|$)",
        r"(?:role|position|job|title)\s*[:\"]?(?:of\s+)?([^,.\n]{5,100}?)(?:\s+(?:at|in|for|\()|[,.\n]|$)",
        r"(?:position|role|opportunity)\s*:\s*([^,.\n]{5,100}?)(?:[,.\n]|$)",
        r"(?:we are looking for|we seek|hiring|now hiring)\s+(?:a|an)?\s+([^,.\n]{5,100}?)(?:\s+(?:to|who|for)|[,.\n]|$)",
        r"\"([^\"]{5,100}?)\"\s+(?:position|role|job)",
        r"(?:interested in|interest in)\s+(?:the\s+)?([^,.\n]{5,100}?)(?:\s+(?:role|position)|[,.\n]|$)",
    ]

    for pat in patterns:
        m = re.search(pat, text, re.I)
        if m:
            role = m.group(1).strip()
            # Remove trailing junk
            role = re.sub(r"\s+(?:at|in|with|for)\s+.*$", "", role, flags=re.I).strip(" .,-\"'")
            # Must have at least 3 chars and max 100
            if role and len(role) >= 3 and len(role) <= 100:
                # Exclude common non-role text
                if not re.search(r"^(email|message|dear|hello|hi|application|thank you)", role, re.I):
                    return role

    return "Unknown Role"


def classify_with_rules(sender, subject, snippet):
    text = f"{subject}\n{snippet}"
    return {
        "company": _guess_company(sender, subject, snippet),
        "role": _guess_role(subject, snippet),
        "status": _match(text, _STATUS_RULES, "Unknown"),
        "source": _match(f"{sender} {text}", _SOURCE_RULES, "Company"),
    }
