"""Job enrichment: skills extraction, seniority classification, experience inference, dedupe keys.

This is the intelligence layer of the Job Intelligence Engine. It normalizes raw job
postings into structured, queryable fields so downstream market intelligence can be
computed quickly and deterministically (no per-job LLM calls at ingest time).
"""

import logging
import re

logger = logging.getLogger(__name__)

# Canonical skill name -> list of aliases matched (case-insensitive, word-bounded).
SKILL_ALIASES: dict[str, list[str]] = {
    # Languages
    "python": ["python"],
    "javascript": ["javascript", "js"],
    "typescript": ["typescript"],
    "java": ["java"],
    "c#": ["c#"],
    "c++": ["c++"],
    "c": ["\\bc\\b"],
    "go": ["\\bgo\\b", "golang"],
    "rust": ["rust"],
    "php": ["php"],
    "ruby": ["ruby"],
    "kotlin": ["kotlin"],
    "swift": ["swift"],
    "scala": ["scala"],
    "dart": ["dart"],
    "sql": ["sql"],
    "nosql": ["nosql"],
    "r": ["\\br\\b"],
    "bash": ["bash", "shell scripting", "shell script"],
    "powershell": ["powershell"],
    "perl": ["perl"],
    "groovy": ["groovy"],
    "elixir": ["elixir"],
    "haskell": ["haskell"],
    "matlab": ["matlab"],
    "solidity": ["solidity"],
    # Frontend
    "react": ["react", "reactjs", "react.js"],
    "react native": ["react native"],
    "next.js": ["next.js", "nextjs"],
    "vue": ["vue", "vuejs", "vue.js"],
    "angular": ["angular"],
    "svelte": ["svelte"],
    "html": ["html"],
    "css": ["css"],
    "tailwind": ["tailwind"],
    "bootstrap": ["bootstrap"],
    "redux": ["redux"],
    "graphql": ["graphql"],
    "webpack": ["webpack"],
    "vite": ["vite"],
    "jquery": ["jquery"],
    "three.js": ["three.js", "threejs"],
    "d3.js": ["d3.js", "d3js"],
    # Backend / APIs
    "node.js": ["node.js", "nodejs", "node"],
    "express": ["express"],
    "django": ["django"],
    "flask": ["flask"],
    "fastapi": ["fastapi"],
    "spring": ["spring", "spring boot"],
    "rails": ["rails", "ruby on rails"],
    "laravel": ["laravel"],
    "asp.net": ["asp.net", "aspnet"],
    "nestjs": ["nestjs"],
    "rest api": ["rest api", "restful", "rest"],
    "microservices": ["microservices", "micro-service"],
    "grpc": ["grpc"],
    "websockets": ["websockets", "web sockets"],
    # Data / ML / AI
    "machine learning": ["machine learning", "ml"],
    "deep learning": ["deep learning"],
    "llm": ["llm", "large language model", "gpt", "openai", "langchain"],
    "data science": ["data science", "data scientist"],
    "data engineering": ["data engineering"],
    "data analysis": ["data analysis", "data analytics"],
    "pandas": ["pandas"],
    "numpy": ["numpy"],
    "scikit-learn": ["scikit-learn", "scikit learn", "sklearn"],
    "tensorflow": ["tensorflow"],
    "pytorch": ["pytorch"],
    "keras": ["keras"],
    "hugging face": ["hugging face", "huggingface", "transformers"],
    "rag": ["rag", "retrieval augmented"],
    "vector database": ["vector database", "vector db", "chromadb", "pinecone", "weaviate", "qdrant", "milvus"],
    "nlp": ["nlp", "natural language processing"],
    "computer vision": ["computer vision"],
    "etl": ["etl", "extract transform load"],
    "spark": ["spark", "apache spark", "pyspark"],
    "kafka": ["kafka", "apache kafka"],
    "airflow": ["airflow"],
    "dbt": ["dbt"],
    "snowflake": ["snowflake"],
    "bigquery": ["bigquery"],
    "redshift": ["redshift"],
    "databricks": ["databricks"],
    "hadoop": ["hadoop"],
    "tableau": ["tableau"],
    "power bi": ["power bi"],
    "looker": ["looker"],
    "excel": ["excel"],
    "statistics": ["statistics", "statistical"],
    "a/b testing": ["a/b testing", "ab testing"],
    # Databases
    "postgresql": ["postgresql", "postgres"],
    "mysql": ["mysql"],
    "mongodb": ["mongodb", "mongo"],
    "redis": ["redis"],
    "elasticsearch": ["elasticsearch", "elastic search"],
    "dynamodb": ["dynamodb", "dynamo db"],
    "cassandra": ["cassandra"],
    "neo4j": ["neo4j"],
    "sqlite": ["sqlite"],
    "oracle": ["oracle"],
    "sql server": ["sql server"],
    "mariadb": ["mariadb"],
    # Cloud / DevOps
    "aws": ["aws", "amazon web services"],
    "azure": ["azure", "microsoft azure"],
    "gcp": ["gcp", "google cloud"],
    "kubernetes": ["kubernetes", "k8s"],
    "docker": ["docker", "containers", "containerization"],
    "terraform": ["terraform"],
    "ansible": ["ansible"],
    "jenkins": ["jenkins"],
    "github actions": ["github actions", "github ci/cd"],
    "gitlab ci": ["gitlab ci", "gitlab"],
    "ci/cd": ["ci/cd", "cicd", "continuous integration"],
    "prometheus": ["prometheus"],
    "grafana": ["grafana"],
    "nginx": ["nginx"],
    "linux": ["linux", "unix"],
    "serverless": ["serverless", "lambda"],
    "system design": ["system design"],
    "networking": ["networking", "network security", "tcp/ip"],
    "cybersecurity": ["cybersecurity", "cyber security", "security"],
    "devsecops": ["devsecops"],
    # Product / Engineering practices
    "agile": ["agile", "scrum"],
    "kanban": ["kanban"],
    "jira": ["jira"],
    "git": ["git"],
    "code review": ["code review"],
    "testing": ["testing", "test automation", "qa", "selenium", "pytest", "jest"],
    "tdd": ["tdd", "test driven development"],
    "ci": ["\\bci\\b"],
    # Business / Management
    "product management": ["product management", "product manager", "pm"],
    "project management": ["project management", "project manager"],
    "program management": ["program management"],
    "people management": ["people management", "people leadership"],
    "stakeholder management": ["stakeholder management", "stakeholders"],
    "communication": ["communication"],
    "presentation": ["presentation", "public speaking"],
    "sales": ["sales", "b2b sales", "saa"],
    "marketing": ["marketing", "digital marketing"],
    "seo": ["seo", "search engine optimization"],
    "growth": ["growth", "growth hacking"],
    "public relations": ["public relations", "pr", "media relations"],
    "copywriting": ["copywriting", "content writing"],
    "ux": ["ux", "user experience"],
    "ui": ["ui", "user interface", "figma"],
    "design": ["design", "graphic design"],
    "research": ["research", "user research"],
    "finance": ["finance", "financial"],
    "accounting": ["accounting"],
    "legal": ["legal", "compliance"],
    "hr": ["hr", "human resources", "recruiting"],
    "data protection": ["data protection", "gdpr", "privacy"],
    "strategy": ["strategy", "strategic"],
    "operations": ["operations", "operational"],
    "analytics": ["analytics", "data-driven"],
    "leadership": ["leadership", "mentorship"],
}

# Skills to match only on word boundaries; aliases already embed boundary markers where needed.
_ALIAS_REGEXES: dict[str, list[re.Pattern]] = {}


def _compile() -> None:
    for skill, aliases in SKILL_ALIASES.items():
        _ALIAS_REGEXES[skill] = [re.compile(rf"(?<![a-z0-9]){alias}(?![a-z0-9])") for alias in aliases]


_compile()

SENIORITY_RULES: list[tuple[re.Pattern, str, int, int | None]] = [
    (re.compile(r"\b(intern|apprentice|graduate|trainee)\b"), "Intern", 0, 0),
    (re.compile(r"\b(junior|jr|jr\.|entry[- ]level)\b"), "Junior", 0, 2),
    (re.compile(r"\b(associate)\b"), "Associate", 0, 3),
    (re.compile(r"\b(mid[- ]level|midlevel|mid)\b"), "Mid-level", 2, 5),
    (re.compile(r"\b(principal)\b"), "Principal", 10, 15),
    (re.compile(r"\b(staff)\b"), "Staff", 8, 12),
    (re.compile(r"\b(lead)\b"), "Lead", 5, 10),
    (re.compile(r"\b(senior|sr|sr\.)\b"), "Senior", 5, 8),
    (re.compile(r"\b(head)\b"), "Head", 8, 15),
    (re.compile(r"\b(director)\b"), "Director", 8, 15),
    (re.compile(r"\b(vice president|vp)\b"), "VP", 10, 18),
    (re.compile(r"\b(chief|cto|cfo|ceo|coo|cmo|officer)\b"), "Executive", 10, 20),
    (re.compile(r"\b(manager)\b"), "Manager", 5, 10),
    (re.compile(r"\blevel[- ]?[67]\b"), "Staff", 8, 12),
    (re.compile(r"\biv\b"), "Staff", 8, 12),
    (re.compile(r"\blevel[- ]?[345]\b"), "Senior", 5, 8),
    (re.compile(r"\biii\b"), "Senior", 5, 8),
    (re.compile(r"\blevel[- ]?2\b"), "Associate", 0, 3),
    (re.compile(r"\bii\b"), "Associate", 0, 3),
]

COUNTRY_ALIASES: list[tuple[tuple[str, ...], str]] = [
    (
        (
            "india",
            "bengaluru",
            "bangalore",
            "mumbai",
            "new delhi",
            "delhi",
            "gurgaon",
            "noida",
            "pune",
            "hyderabad",
            "chennai",
            "kolkata",
            "ahmedabad",
            "remote (india)",
        ),
        "India",
    ),
    (
        (
            "germany",
            "berlin",
            "munich",
            "münchen",
            "frankfurt",
            "hamburg",
            "stuttgart",
            "cologne",
            "köln",
            "leipzig",
            "dresden",
            "deu",
            "remote (germany)",
        ),
        "Germany",
    ),
    (
        (
            "united states",
            "usa",
            "u.s.a.",
            "new york",
            "san francisco",
            "austin",
            "seattle",
            "chicago",
            "boston",
            "los angeles",
            "california",
            "texas",
            "washington dc",
            "remote (us)",
        ),
        "United States",
    ),
    (
        (
            "united kingdom",
            "england",
            "scotland",
            "london",
            "covent garden",
            "bristol",
            "manchester",
            "gbr",
            "remote (uk)",
        ),
        "United Kingdom",
    ),
    (("canada", "toronto", "vancouver", "montreal", "remote (canada)"), "Canada"),
    (("australia", "sydney", "melbourne", "remote (australia)"), "Australia"),
    (("netherlands", "amsterdam", "remote (netherlands)"), "Netherlands"),
    (("france", "paris", "remote (france)"), "France"),
    (("spain", "madrid", "barcelona", "remote (spain)"), "Spain"),
    (("portugal", "lisbon", "porto", "remote (portugal)"), "Portugal"),
    (("switzerland", "zurich", "geneva", "remote (switzerland)"), "Switzerland"),
    (("poland", "warsaw", "krakow", "remote (poland)"), "Poland"),
    (("ireland", "dublin", "remote (ireland)"), "Ireland"),
    (("sweden", "stockholm", "remote (sweden)"), "Sweden"),
    (("remote", "anywhere", "worldwide", "global", "emea", "apac", "europe", "eu"), "Remote"),
]

_COUNTRY_RE = [
    (re.compile(rf"(?<![a-z]){re.escape(alias)}(?![a-z])"), country)
    for aliases, country in COUNTRY_ALIASES
    for alias in aliases
]


def infer_country(location: str | None) -> str | None:
    """Infer an ISO-style country name from a free-text location string."""
    if not location:
        return None
    lowered = location.lower()
    for pattern, country in _COUNTRY_RE:
        if pattern.search(lowered):
            return country
    return None

MAX_SKILLS_PER_JOB = 30


def extract_skills(text: str | None) -> list[str]:
    """Return canonical skill names present in the text, ordered by first match."""
    if not text:
        return []
    lowered = text.lower()
    found: list[str] = []
    seen: set[str] = set()
    for skill, patterns in _ALIAS_REGEXES.items():
        if skill in seen:
            continue
        if any(p.search(lowered) for p in patterns):
            found.append(skill)
            seen.add(skill)
        if len(found) >= MAX_SKILLS_PER_JOB:
            break
    return found


def classify_seniority(title: str | None) -> str | None:
    """Classify a job title into a seniority band. Returns None when unknown."""
    if not title:
        return None
    lowered = title.lower()
    for pattern, band, _min, _max in SENIORITY_RULES:
        if pattern.search(lowered):
            return band
    return None


def experience_range(seniority: str | None) -> tuple[int | None, int | None]:
    """Map a seniority band to a (min_years, max_years) experience range."""
    if not seniority:
        return None, None
    for _pattern, band, min_years, max_years in SENIORITY_RULES:
        if band == seniority:
            return min_years, max_years
    return None, None


def make_dedupe_key(title: str | None, company: str | None) -> str:
    """Normalize title + company into a stable key for cross-source deduplication."""
    def _normalize(value: str | None) -> str:
        if not value:
            return ""
        text = value.lower()
        text = re.sub(r"\(.*?\)", " ", text)
        text = re.sub(r"[^a-z0-9 ]", " ", text)
        text = re.sub(r"\b(remote|hybrid|india|uk|us|usa|germany|german|bengaluru|bangalore|mumbai|delhi|berlin|london)\b", " ", text)
        return re.sub(r"\s+", " ", text).strip()

    title_norm = _normalize(title)
    company_norm = _normalize(company)
    if not title_norm:
        return ""
    return f"{title_norm}|{company_norm}"


def enrich(
    title: str | None,
    description: str | None,
    requirements: str | None = None,
    company: str | None = None,
    location: str | None = None,
) -> dict:
    """Compute all enrichment fields for a job posting."""
    seniority = classify_seniority(title)
    experience_min, experience_max = experience_range(seniority)
    skills = extract_skills(" ".join(filter(None, [title, description, requirements])))
    return {
        "seniority": seniority,
        "experience_min": experience_min,
        "experience_max": experience_max,
        "skills_required": ",".join(skills) if skills else None,
        "dedupe_key": make_dedupe_key(title, company),
        "country": infer_country(location),
    }
