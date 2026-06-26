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
    ("Offer", r"pleased to offer|offer of employment|formal offer|we'?d like to offer you"),
    ("Rejected", r"regret to inform|unfortunately|not been (successful|selected)|"
                 r"not successful|decided not to (proceed|move ahead)|not to progress|"
                 r"other candidate|unsuccessful (on this occasion|in this|at this)|"
                 r"will not be progressing|decided to (move ahead|choose another)|"
                 r"only contact(ing)? .{0,30}shortlist"),
    ("Withdrawn", r"position (has been )?(closed|withdrawn|filled)|no longer (available|recruiting)|"
                  r"role (has been )?closed|ending the search"),
    ("Interview", r"\binterview\b|phone (chat|screen|call|interview)|"
                  r"schedule a (call|time|chat)|book a time|are you available|"
                  r"would (love|like) to (have a|chat|speak|invite)|set up a time|next round"),
    ("Viewed", r"your application was viewed|viewed by"),
    ("Awaiting", r"thank you for applying|thanks for applying|received your application|"
                 r"application (was )?(sent|submitted|received)|acknowledge receipt"),
]

_SOURCE_RULES = [
    ("LinkedIn", r"your application was sent to|linkedin"),
    ("Indeed", r"indeed\.com|your application to .+ at "),
    ("Seek", r"seek\.com|hays\.com|submitted successfully.*copy of your application data|employment hero"),
]


def _match(text, rules, default):
    for label, pattern in rules:
        if re.search(pattern, text, re.I):
            return label
    return default


def _guess_company(sender, subject, snippet):
    m = re.search(r"application was sent to ([^\n͏]+?)(?: ͏|$)", snippet, re.I)
    if m:
        return m.group(1).strip()
    m = re.search(r"application to .+? at ([A-Z][\w&.\- ]+)", snippet)
    if m:
        return m.group(1).strip()
    # fall back to sender display name, else domain
    name = re.sub(r"<.*?>", "", sender).strip().strip('"')
    if name and "@" not in name and "noreply" not in name.lower():
        return name
    dom = re.search(r"@([\w.\-]+)", sender)
    return dom.group(1).split(".")[0].title() if dom else "Unknown"


def _guess_role(subject, snippet):
    text = f"{subject} {snippet}"
    for pat in [
        r"appl(?:y|ied|ication) for (?:the (?:role|position) of )?([A-Z][\w/&.\-() ]{3,60})",
        r"position of ([A-Z][\w/&.\-() ]{3,60})",
        r"the ([A-Z][\w/&.\-() ]{3,60}?) (?:position|role|opportunity)",
        r"interest in (?:the )?([A-Z][\w/&.\-() ]{3,60}?) (?:position|role)",
    ]:
        m = re.search(pat, text)
        if m:
            return re.sub(r"\s+(at|with)\b.*$", "", m.group(1)).strip(" .-")
    return "(role unparsed)"


def classify_with_rules(sender, subject, snippet):
    text = f"{subject}\n{snippet}"
    return {
        "company": _guess_company(sender, subject, snippet),
        "role": _guess_role(subject, snippet),
        "status": _match(text, _STATUS_RULES, "Unknown"),
        "source": _match(f"{sender} {text}", _SOURCE_RULES, "Company"),
    }
