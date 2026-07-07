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
    ("Indeed",   r"indeed\.com|from indeed|via indeed|indeedemail|on indeed"),
    ("Seek",     r"seek\.com|seek\.com\.au|seek\.co\.nz|hays\.com|employment hero|"
                 r"from seek|via seek|seek\.asia"),
    ("Glassdoor",   r"glassdoor\.com|from glassdoor|via glassdoor"),
    ("ZipRecruiter",r"ziprecruiter\.com|from ziprecruiter|via ziprecruiter"),
    ("AngelList",   r"angellist\.com|angel\.co|from angellist|via angellist|wellfound\.com"),
    ("Workable",    r"workable\.com|from workable|via workable|apply on workable"),
    ("Lever",       r"lever\.co|lever-hosted\.appspot\.com|from lever|via lever"),
    ("Greenhouse",  r"greenhouse\.io|from greenhouse|via greenhouse"),
    ("Talentdesk",  r"talentdesk|from talentdesk|via talentdesk"),
    ("Twitter/X Jobs",  r"twitter\.com.*jobs|x\.com.*jobs"),
    ("GitHub Jobs",     r"github\.com.*jobs"),
    ("Stack Overflow",  r"stackoverflow\.com"),
    ("Company", r""),
]

# Domains that are job boards / ATS / generic email providers — not real companies
_SKIP_DOMAINS = {
    "linkedin", "indeed", "seek", "glassdoor", "ziprecruiter", "angel", "wellfound",
    "workable", "lever", "greenhouse", "talentdesk", "twitter", "github",
    "stackoverflow", "gmail", "outlook", "yahoo", "hotmail", "aol",
    "mail", "noreply", "no-reply", "notifications", "mailer", "donotreply",
    "alert", "notification", "careers", "jobs", "recruit", "hr", "apply",
    "hays", "workday", "bamboohr", "taleo", "icims", "successfactors",
    "smartrecruiters", "jobvite", "ultipro", "kronos", "myworkdayjobs",
    "seek", "talentpropeller", "aiapply",
}

# Subjects that prove this is NOT a job application — skip entirely
_JUNK_SUBJECT_RE = re.compile(
    r"linkedin job alert|linkedin job recommendation|"
    r"jobs? (you may|for you|based on|near you)|"
    r"new jobs (for|based|near)|"
    r"linkedin learning|linkedin premium|"
    r"linkedin.*(digest|weekly|news|newsletter)|"
    r"(new |)connection request|sent you a (message|connection)|"
    r"who viewed your profile|people (are |)looking at your profile|"
    r"you have \d+ new (connection|message)|"
    r"(flight|hotel|travel|booking).*(confirm|receipt)|"
    r"(confirm|verify|reset|activate) your (email|account|password)|"
    r"your (account|password) (has been |)(created|reset|changed)|"
    r"welcome to (sign|register|creat)|"
    r"salary (report|survey|benchmark|guide)|"
    r"market (report|compensation)|"
    r"ai (agent|apply|job search).*on the case|"
    r"refer a friend|"
    r"see who.?s hiring|"
    r"^\s*(indeed|azure|design|hiring)\s*$",
    re.I
)


def is_junk_email(sender, subject, snippet):
    """Return True if this is NOT a real job application — caller should skip it."""
    if _JUNK_SUBJECT_RE.search(subject):
        return True

    # Personal LinkedIn message (first + last name via LinkedIn) — not a company
    via_m = re.search(r'^["\']?([^"\'<\n]+?)["\']?\s+via\s+linkedin\s*$', subject.strip(), re.I)
    if via_m:
        name = via_m.group(1).strip()
        # Two-word proper name = a person, not a company
        if re.match(r'^[A-Z][a-z]+ [A-Z][a-z]+$', name):
            return True

    # Non-job snippet patterns
    low = f"{subject} {snippet}".lower()
    if re.search(r"ai agent.*job|your.*ai.*is.*(on the case|searching|looking)", low):
        return True
    if re.search(r"booking.*flights|your flight (is |)confirmed", low):
        return True

    return False


def _match(text, rules, default):
    for label, pattern in rules:
        if re.search(pattern, text, re.I):
            return label
    return default


def _clean(name):
    """Strip noise and validate a candidate name string."""
    if not name:
        return None
    name = name.strip().strip('"\'')
    # Trim trailing junk phrases
    name = re.sub(
        r'\s*(?:your application|we appreciate|while your|at this time|shortly we|'
        r'after careful|we will carefully|please note|thank you for).*$',
        '', name, flags=re.I
    ).strip()
    if not name or len(name) < 2 or len(name) > 80:
        return None
    # Must not start with a conjunction / pronoun
    if re.match(r'^(for|the|a|an|and|or|at|in|on|to|with|your|we|our|dear|'
                r'hi|hello|thank|this|that|so|much)\b', name, re.I):
        return None
    return name


def _from_linkedin_subject(subject):
    """Return (company, role) pulled from LinkedIn email subjects, or (None, None)."""

    # "Your application to [Role] at [Company]"
    m = re.search(r"your application to (.+?) at (.+?)$", subject, re.I)
    if m:
        return _clean(m.group(2)), _clean(m.group(1))

    # "Your application was sent to [Company]"
    m = re.search(r"your application was sent to (.+?)$", subject, re.I)
    if m:
        return _clean(m.group(1)), None

    # "CompanyName Your application was sent to CompanyName" (LinkedIn duplicate format)
    m = re.search(r"^(.+?)\s+your application was sent to \1\s*$", subject, re.I)
    if m:
        return _clean(m.group(1)), None

    # "[Company] Your application to [Role] at [Company]" (LinkedIn snippet-subject)
    m = re.search(r"^([A-Z][A-Za-z\s\-&.']+?)\s+your application to (.+?) at \1", subject, re.I)
    if m:
        return _clean(m.group(1)), _clean(m.group(2))

    # "application to [Role] at [Company]" anywhere in subject/snippet
    m = re.search(r"application (?:to|for) (?:the )?(.+?) at ([A-Z][A-Za-z\s\-&.']{2,50}?)(?:\.|,|$)", subject, re.I)
    if m:
        return _clean(m.group(2)), _clean(m.group(1))

    return None, None


def _guess_company(sender, subject, snippet):
    """Return best company name or 'Unknown'."""

    # 1. LinkedIn subject patterns (very reliable)
    company, _ = _from_linkedin_subject(subject)
    if company:
        return company

    # 2. Sender email domain
    dom = re.search(r"@([\w.\-]+\.\w+)", sender)
    if dom:
        parts = dom.group(1).lower().split(".")
        base = parts[-2] if len(parts) >= 2 else parts[0]
        if base not in _SKIP_DOMAINS and len(base) >= 2:
            return base.replace("-", " ").title()

    # 3. "[Company] via LinkedIn" in sender string
    via = re.search(r'^["\']?(.+?)["\']?\s+via\s+linkedin\s*(?:<|$)', sender, re.I)
    if via:
        c = _clean(via.group(1))
        if c:
            return c

    # 4. Sender display name — must look like a company, not a generic phrase
    disp = re.sub(r"<[^>]+>", "", sender).strip().strip('"\'')
    if disp and "@" not in disp and 2 <= len(disp) <= 60 and re.match(r'^[A-Z]', disp):
        if not re.search(
            r'\b(job|jobs|alert|alerts|notification|noreply|no.?reply|'
            r'team|recruiting|recruitment|talent\s+acquisition|careers|career|'
            r'learning|premium|recommendation|recommendations|digest|news|'
            r'weekly|updates?|newsletter|hr|human\s+resources|hiring|'
            r'support|pass|seek|linkedin|indeed|glassdoor)\b',
            disp, re.I
        ):
            return disp

    # 5. Snippet: "CompanyName. We / Your / Dear..."
    m = re.match(r"^([A-Z][a-zA-Z0-9\s\-&.']{2,40})\.\s+(?:We|Your|Dear|Thank|Hi|This)", snippet)
    if m:
        c = _clean(m.group(1))
        if c:
            return c

    # 6. Snippet: "with/at CompanyName Shortly/We/Our"
    m = re.search(
        r'\b(?:with|at)\s+([A-Z][a-zA-Z0-9\s\-&.\']{2,50}?)'
        r'(?:\.\s|\,\s|\s+(?:Shortly|We\s|Our\s|The\s+team|Please))',
        snippet
    )
    if m:
        c = _clean(m.group(1))
        if c and not re.search(r'\b(we|the|our|your|this|that|hiring|application|regard)\b', c, re.I):
            return c

    # 7. Snippet: "from CompanyName Hi/Dear Firstname"
    m = re.search(r'from ([A-Z][a-zA-Z0-9\s\-&.\']{2,40}?)\s+(?:Hi|Dear|Hello)\b', snippet)
    if m:
        c = _clean(m.group(1))
        if c:
            return c

    return "Unknown"


def _guess_role(subject, snippet):
    """Return best role/title or 'Unknown'."""

    # 1. LinkedIn subject patterns (very reliable)
    _, role = _from_linkedin_subject(subject)
    if role and 3 <= len(role) <= 90:
        return role

    text = f"{subject}\n{snippet}"

    patterns = [
        # "application to/for the [Role] position/role"
        r"application (?:to|for) (?:the )?([A-Za-z][A-Za-z\s\-/&.()\d]{3,70}?) (?:position|role|opportunity)(?:\s+at|\s+with|\.|,|$)",
        # "position of [Role]"
        r"position of ([A-Za-z][A-Za-z\s\-/&.()\d]{3,70}?)(?:\s+(?:at|with|in)|\.|,|$|\n)",
        # "for the [Role] role/position at"
        r"for (?:the )?(?:role of )?([A-Za-z][A-Za-z\s\-/&.()\d]{3,70}?) (?:role|position)(?:\s+at|\.|,|$)",
        # "to/for [Role] at/with Company" in snippet
        r"(?:to|for) (?:the )?(?:role of |position of )?([A-Za-z][A-Za-z\s\-/&.()\d]{4,70}?) (?:at|with) [A-Z]",
        # "role: [Role]" / "position: [Role]"
        r"(?:role|position|title|applying for)[:\s]+([A-Za-z][A-Za-z\s\-/&.()\d]{3,70}?)(?:\s+at|\s+with|\.|,|\n|$)",
        # Titles starting with common seniority/tech keywords
        r"((?:cloud|senior|junior|lead|staff|graduate|entry.level|desktop|it\s+|systems?\s+|network|software|"
        r"devops|site reliability|data|business|project|technical|technology|service desk|help desk|"
        r"l1|l2|l3|level [123]|tier [123]|field|customer|sales|security|infrastructure|platform|"
        r"full.?stack|front.?end|back.?end|mobile)\s+[A-Za-z\s\-/&.()\d]{3,60}?)"
        r"(?:\s+at\s|\s+with\s|\s+role\s|\s+position\s|\.|,|$)",
    ]

    for pat in patterns:
        m = re.search(pat, text, re.I | re.M)
        if m:
            role = m.group(1).strip().title()
            if 3 <= len(role) <= 90:
                if not re.match(r'^(your|the|a|an|and|or|for|with|at|in|we|thank|dear|hi|hello|this)', role, re.I):
                    if not re.search(r'\d{4}|http|www\.', role):
                        return role

    return "Unknown"


def classify_with_rules(sender, subject, snippet):
    text = f"{subject}\n{snippet}"
    return {
        "company": _guess_company(sender, subject, snippet),
        "role":    _guess_role(subject, snippet),
        "status":  _match(text, _STATUS_RULES, "Unknown"),
        "source":  _match(f"{sender} {text}", _SOURCE_RULES, "Company"),
    }
