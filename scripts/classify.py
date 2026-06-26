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

# order matters: a post-interview rejection mentions "interview" AND "regret",
# so Offer/Rejected are checked before Interview.
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

# Job board and source identifiers
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
    text = f"{sender} {subject} {snippet}"

    # Try to extract company from explicit mentions
    patterns = [
        r"application was sent to ([^\n͏]+?)(?: ͏|$)",  # LinkedIn format
        r"application to .+? at ([A-Z][\w&.\-'() ]+)",  # Indeed format
        r"(?:position|role) at ([A-Z][\w&.\-'() ]+)",
        r"company:?\s*([A-Z][\w&.\-'() ]+)",
        r"applying to\s+([A-Z][\w&.\-'() ]+)",
        r"(?:congratulations|thank you),?\s*([A-Z][\w&.\-'() ]+)",
    ]

    for pat in patterns:
        m = re.search(pat, text, re.I)
        if m:
            company = m.group(1).strip()
            # Clean up common suffixes
            company = re.sub(r"\s+(for|in|recruiting|careers|jobs).*$", "", company, flags=re.I)
            return company.strip(" .,-")

    # Fall back to sender display name
    name = re.sub(r"<.*?>", "", sender).strip().strip('"')
    if name and "@" not in name and "noreply" not in name.lower() and len(name) > 2:
        return name

    # Fall back to domain name
    dom = re.search(r"@([\w.\-]+)", sender)
    if dom:
        domain = dom.group(1).split(".")[0].title()
        # Don't return generic domains
        if domain.lower() not in ["gmail", "outlook", "yahoo", "hotmail", "aol", "mail", "email"]:
            return domain

    return "Unknown"


def _guess_role(subject, snippet):
    text = f"{subject} {snippet}"
    patterns = [
        r"appl(?:y|ied|ication) for (?:the (?:role|position|job) (?:of )?)?([A-Z][\w/&.\-() ]{3,70}?)(?:\s+(?:at|with|in)|$)",
        r"position of ([A-Z][\w/&.\-() ]{3,70}?)(?:\s+(?:at|with|in)|$)",
        r"the ([A-Z][\w/&.\-() ]{3,70}?) (?:position|role|opportunity|job)(?:\s+(?:at|with|in)|$)",
        r"interest in (?:the )?([A-Z][\w/&.\-() ]{3,70}?) (?:position|role|opportunity)",
        r"(?:role|position):\s*([A-Z][\w/&.\-() ]{3,70}?)\s*(?:\n|$)",
        r"(?:job title|job|title):\s*([A-Z][\w/&.\-() ]{3,70}?)(?:\s|$|,)",
        r"[Oo]pportunity:?\s+([A-Z][\w/&.\-() ]{3,70}?)(?:\s|$|,)",
        r"(?:for the role of|for a|looking for)\s+([A-Z][\w/&.\-() ]{3,70}?)(?:\s|$|,)",
    ]
    for pat in patterns:
        m = re.search(pat, text)
        if m:
            role = re.sub(r"\s+(at|with|in|for|and)\b.*$", "", m.group(1), flags=re.I).strip(" .,-")
            if role and len(role) > 2:
                return role
    return "(role unparsed)"


def classify_with_rules(sender, subject, snippet):
    text = f"{subject}\n{snippet}"
    return {
        "company": _guess_company(sender, subject, snippet),
        "role": _guess_role(subject, snippet),
        "status": _match(text, _STATUS_RULES, "Unknown"),
        "source": _match(f"{sender} {text}", _SOURCE_RULES, "Company"),
    }
