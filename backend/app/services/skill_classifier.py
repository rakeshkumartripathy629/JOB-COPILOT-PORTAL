"""Requirement classification for the advanced matching engine.

Rules that keep matching honest:
- DIRECT_MATCH requires the *same* canonical skill in the user's profile.
- RELATED_MATCH only for known related-skill pairs (MongoDB ~ PostgreSQL, Docker ~ K8s).
  A related skill is NEVER a direct match and NEVER satisfies a critical requirement.
- PARTIAL_MATCH only on genuine token overlap; generic terms like "database" never
  become a direct match for a concrete skill like PostgreSQL.
- NO_EVIDENCE when nothing backs the requirement.
"""

from __future__ import annotations

import re

from app.services.job_enrichment_service import SKILL_ALIASES
from app.services.job_match_service import SOFT_SKILLS

DIRECT_MATCH = "DIRECT_MATCH"
RELATED_MATCH = "RELATED_MATCH"
PARTIAL_MATCH = "PARTIAL_MATCH"
NO_EVIDENCE = "NO_EVIDENCE"

#: Skills that are generic umbrella terms; they can never be a direct match for a
#: concrete skill the user holds (e.g. "database" vs PostgreSQL).
GENERIC_SKILLS = {
    "database", "databases", "programming", "software", "software development", "it",
    "technology", "computer science", "coding", "web development", "engineering",
    "design", "architecture", "framework", "language", "api", "data", "cloud",
}

#: Canonical skill -> canonical skills that count as related evidence (never direct).
RELATED_SKILLS: dict[str, set[str]] = {
    # Languages
    "javascript": {"typescript", "node.js", "react", "vue", "angular", "svelte", "next.js", "jquery"},
    "typescript": {"javascript", "node.js", "react", "angular", "vue", "svelte", "next.js"},
    "python": {"django", "flask", "fastapi", "pandas", "numpy", "scikit-learn", "pytorch",
               "tensorflow", "machine learning", "data science", "r", "julia", "pyspark"},
    "java": {"kotlin", "spring", "scala", "groovy", "android", "c#"},
    "go": {"rust", "c++", "java", "python"},
    "golang": {"go", "rust", "c++", "java", "python"},
    "rust": {"go", "c++", "c", "golang"},
    "c++": {"c", "rust", "go", "python", "java", "c#"},
    "c": {"c++", "rust", "go"},
    "c#": {"java", "asp.net", "kotlin", "scala"},
    "ruby": {"rails", "python", "php", "javascript"},
    "php": {"laravel", "ruby", "python", "javascript"},
    "kotlin": {"java", "swift", "android", "flutter", "dart"},
    "swift": {"kotlin", "ios", "objective-c", "react native", "flutter"},
    "dart": {"flutter", "kotlin", "swift"},
    "scala": {"java", "spark", "kotlin"},
    "groovy": {"java", "jenkins", "gradle"},
    "r": {"python", "statistics", "data science", "pandas", "data analysis"},
    "julia": {"python", "r"},
    "matlab": {"numpy", "python"},
    "perl": {"python", "bash", "ruby"},
    # Frameworks / backend
    "node.js": {"javascript", "typescript", "express", "nestjs", "next.js", "react", "vue", "deno"},
    "express": {"node.js", "nestjs", "fastapi", "flask", "spring", "django"},
    "nestjs": {"node.js", "express", "spring", "django", "fastapi"},
    "django": {"flask", "fastapi", "python", "rails", "laravel", "spring", "express"},
    "flask": {"django", "fastapi", "python", "express", "spring", "rails"},
    "fastapi": {"django", "flask", "express", "nestjs", "python", "spring"},
    "spring": {"java", "nestjs", "django", "flask", "fastapi", "express", "rails", "laravel", "asp.net"},
    "rails": {"ruby", "django", "laravel", "flask", "spring", "asp.net"},
    "laravel": {"php", "django", "rails", "flask", "spring", "asp.net"},
    "asp.net": {"c#", "spring", "django", "rails", "laravel"},
    "rest api": {"graphql", "grpc", "soap", "websockets", "express", "fastapi", "django", "flask", "spring", "nestjs", "node.js"},
    "graphql": {"rest api", "grpc", "websockets", "apollo", "hasura"},
    "grpc": {"rest api", "graphql", "websockets", "protobuf"},
    "websockets": {"rest api", "grpc", "socket.io", "node.js"},
    "microservices": {"docker", "kubernetes", "kafka", "rest api", "grpc", "aws", "spring", "distributed systems"},
    # Frontend
    "react": {"next.js", "vue", "angular", "svelte", "react native", "javascript", "typescript"},
    "react native": {"react", "flutter", "kotlin", "swift", "android", "ios"},
    "next.js": {"react", "vue", "angular", "svelte", "node.js", "typescript"},
    "vue": {"react", "angular", "svelte", "javascript", "typescript", "next.js"},
    "angular": {"react", "vue", "svelte", "javascript", "typescript"},
    "svelte": {"react", "vue", "angular", "javascript", "typescript"},
    "flutter": {"react native", "kotlin", "swift", "android", "ios", "dart"},
    "html": {"css", "javascript", "web"},
    "css": {"html", "tailwind", "bootstrap", "sass", "less"},
    "tailwind": {"css", "bootstrap", "ui"},
    "bootstrap": {"css", "tailwind", "ui"},
    # Data / ML / AI
    "machine learning": {"deep learning", "data science", "python", "pytorch", "tensorflow", "nlp",
                         "computer vision", "rag", "llm", "statistics", "scikit-learn", "data engineering"},
    "deep learning": {"machine learning", "pytorch", "tensorflow", "keras", "computer vision", "nlp", "rag", "llm"},
    "pytorch": {"tensorflow", "keras", "machine learning", "deep learning", "scikit-learn", "jax"},
    "tensorflow": {"pytorch", "keras", "machine learning", "deep learning", "scikit-learn"},
    "keras": {"tensorflow", "pytorch", "machine learning", "deep learning"},
    "scikit-learn": {"pandas", "numpy", "machine learning", "data science", "statistics", "pytorch", "tensorflow"},
    "pandas": {"numpy", "scikit-learn", "data science", "data analysis", "excel", "r"},
    "numpy": {"pandas", "scikit-learn", "data science", "matlab"},
    "nlp": {"llm", "rag", "machine learning", "deep learning", "computer vision", "transformers", "python"},
    "llm": {"rag", "nlp", "machine learning", "deep learning", "transformers", "python"},
    "rag": {"llm", "nlp", "vector database", "python", "transformers", "machine learning"},
    "computer vision": {"machine learning", "deep learning", "opencv", "nlp"},
    "transformers": {"llm", "nlp", "hugging face", "machine learning", "deep learning", "pytorch"},
    "hugging face": {"transformers", "llm", "nlp", "python", "pytorch", "tensorflow"},
    "opencv": {"computer vision", "python", "deep learning"},
    "data science": {"machine learning", "data analysis", "statistics", "python", "pandas", "data engineering", "sql", "r"},
    "data engineering": {"etl", "spark", "airflow", "sql", "data science", "data analysis", "kafka", "dbt",
                         "snowflake", "bigquery", "redshift", "databricks", "hadoop"},
    "data analysis": {"data science", "sql", "excel", "pandas", "statistics", "tableau", "power bi", "looker", "data engineering"},
    "etl": {"spark", "airflow", "dbt", "data engineering", "sql", "kafka", "hadoop"},
    "spark": {"etl", "data engineering", "hadoop", "pyspark", "databricks", "kafka", "airflow"},
    "pyspark": {"spark", "python", "data engineering", "hadoop", "databricks"},
    "kafka": {"rabbitmq", "pulsar", "spark", "data engineering", "streaming", "airflow"},
    "airflow": {"etl", "dbt", "data engineering", "spark", "prefect", "dagster", "luigi"},
    "dbt": {"airflow", "snowflake", "bigquery", "redshift", "etl", "data engineering"},
    "snowflake": {"bigquery", "redshift", "databricks", "dbt", "data engineering", "sql"},
    "bigquery": {"snowflake", "redshift", "databricks", "sql", "data engineering", "gcp"},
    "redshift": {"snowflake", "bigquery", "aws", "sql", "data engineering"},
    "databricks": {"spark", "snowflake", "bigquery", "data engineering", "redshift"},
    "hadoop": {"spark", "etl", "data engineering", "hive", "hbase"},
    "tableau": {"power bi", "looker", "data analysis", "data science", "excel"},
    "power bi": {"tableau", "looker", "data analysis", "excel", "data science"},
    "looker": {"tableau", "power bi", "data analysis", "sql"},
    "excel": {"google sheets", "tableau", "power bi", "data analysis", "pandas", "sql"},
    "statistics": {"data science", "data analysis", "machine learning", "r", "pandas"},
    # Databases
    "mongodb": {"postgresql", "mysql", "sql", "sqlite", "redis", "dynamodb", "cassandra", "oracle",
                "sql server", "mariadb", "elasticsearch", "nosql", "couchbase"},
    "postgresql": {"mongodb", "mysql", "sql", "sqlite", "dynamodb", "cassandra", "oracle", "sql server",
                   "mariadb", "redis", "cockroachdb", "pgvector"},
    "mysql": {"postgresql", "mongodb", "sql", "sqlite", "mariadb", "dynamodb", "oracle", "sql server"},
    "sql": {"postgresql", "mysql", "mongodb", "sqlite", "mariadb", "dynamodb", "oracle", "sql server",
            "bigquery", "redshift", "snowflake"},
    "sqlite": {"postgresql", "mysql", "sql"},
    "redis": {"elasticsearch", "mongodb", "dynamodb", "memcached", "caching"},
    "memcached": {"redis", "caching"},
    "elasticsearch": {"redis", "vector database", "opensearch", "solr", "algolia", "meilisearch"},
    "opensearch": {"elasticsearch", "vector database"},
    "solr": {"elasticsearch", "lucene"},
    "dynamodb": {"mongodb", "cassandra", "redis", "postgresql", "sql"},
    "cassandra": {"dynamodb", "mongodb", "hbase", "nosql", "couchbase"},
    "oracle": {"postgresql", "mysql", "sql server", "sql"},
    "sql server": {"postgresql", "mysql", "oracle", "sql"},
    "mariadb": {"mysql", "postgresql", "sql"},
    "nosql": {"mongodb", "cassandra", "dynamodb", "redis", "couchbase", "neo4j", "elasticsearch"},
    "neo4j": {"graphql", "nosql", "mongodb"},
    "couchbase": {"mongodb", "cassandra", "redis", "nosql", "dynamodb"},
    "hbase": {"hadoop", "cassandra", "nosql"},
    "cockroachdb": {"postgresql", "sql", "distributed systems"},
    "vector database": {"elasticsearch", "redis", "faiss", "chroma", "pinecone", "weaviate", "qdrant", "milvus", "pgvector"},
    "chroma": {"vector database", "pgvector", "pinecone", "weaviate", "qdrant", "milvus", "faiss"},
    "pinecone": {"vector database", "chroma", "weaviate", "qdrant", "milvus", "faiss"},
    "weaviate": {"vector database", "chroma", "pinecone", "qdrant", "milvus", "faiss"},
    "qdrant": {"vector database", "chroma", "pinecone", "weaviate", "milvus", "faiss"},
    "milvus": {"vector database", "chroma", "pinecone", "weaviate", "qdrant", "faiss"},
    "faiss": {"vector database", "chroma", "pinecone", "weaviate", "qdrant", "milvus"},
    "pgvector": {"postgresql", "vector database", "rag"},
    # Cloud / DevOps
    "aws": {"azure", "gcp", "cloud", "serverless", "lambda"},
    "azure": {"aws", "gcp", "cloud", "serverless"},
    "gcp": {"aws", "azure", "cloud", "serverless"},
    "cloud": {"aws", "azure", "gcp", "serverless"},
    "serverless": {"aws", "lambda", "azure", "gcp", "cloud", "kubernetes"},
    "lambda": {"serverless", "aws", "cloud", "azure functions"},
    "docker": {"kubernetes", "podman", "containerd", "rancher", "helm", "ecs", "docker compose"},
    "kubernetes": {"docker", "helm", "rancher", "ecs", "openshift", "containerd", "podman", "kubectl"},
    "docker compose": {"docker", "kubernetes", "containerd"},
    "helm": {"kubernetes", "rancher", "terraform", "docker"},
    "podman": {"docker", "kubernetes", "containerd"},
    "containerd": {"docker", "kubernetes", "podman"},
    "rancher": {"kubernetes", "docker"},
    "ecs": {"kubernetes", "docker", "aws", "eks", "fargate"},
    "openshift": {"kubernetes", "docker"},
    "terraform": {"ansible", "cloudformation", "pulumi", "aws", "azure", "gcp", "helm", "kubernetes"},
    "ansible": {"terraform", "puppet", "chef", "saltstack"},
    "cloudformation": {"terraform", "aws", "pulumi"},
    "pulumi": {"terraform", "cloudformation", "aws", "azure", "gcp"},
    "ci/cd": {"github actions", "gitlab ci", "jenkins", "circleci", "azure devops"},
    "jenkins": {"github actions", "gitlab ci", "circleci", "ci/cd", "azure devops"},
    "github actions": {"jenkins", "gitlab ci", "circleci", "ci/cd"},
    "gitlab ci": {"jenkins", "github actions", "circleci", "ci/cd"},
    "prometheus": {"grafana", "cloudwatch", "datadog", "monitoring", "sre"},
    "grafana": {"prometheus", "cloudwatch", "datadog", "monitoring"},
    "cloudwatch": {"prometheus", "grafana", "datadog", "aws"},
    "datadog": {"prometheus", "grafana", "new relic", "monitoring"},
    "monitoring": {"prometheus", "grafana", "datadog", "sre", "cloudwatch", "observability"},
    "observability": {"monitoring", "grafana", "prometheus", "datadog", "distributed tracing"},
    "linux": {"unix", "bash", "devops", "sre"},
    "bash": {"powershell", "linux", "unix", "shell"},
    "powershell": {"bash", "windows", "azure", "shell"},
    "networking": {"linux", "aws", "azure", "gcp", "cybersecurity"},
    "cybersecurity": {"networking", "devsecops", "security"},
    "devsecops": {"cybersecurity", "devops", "security", "ci/cd"},
    "nginx": {"load balancing", "linux", "reverse proxy"},
    "git": {"github", "gitlab", "bitbucket", "github actions", "gitlab ci"},
    # Product / process / soft
    "agile": {"scrum", "kanban", "jira", "project management"},
    "scrum": {"agile", "kanban", "jira", "project management"},
    "kanban": {"agile", "scrum", "jira"},
    "product management": {"project management", "product owner", "program management", "agile", "analytics"},
    "product owner": {"product management", "scrum", "agile"},
    "project management": {"product management", "program management", "agile", "scrum", "jira"},
    "program management": {"project management", "product management"},
    "people management": {"leadership", "mentorship"},
    "leadership": {"people management", "mentorship", "strategy", "stakeholder management"},
    "mentorship": {"leadership", "people management"},
    "stakeholder management": {"communication", "leadership", "presentation"},
    "communication": {"stakeholder management", "presentation", "collaboration", "teamwork"},
    "presentation": {"communication", "stakeholder management"},
    "analytics": {"data analysis", "data science", "sql", "product management", "a/b testing", "tableau"},
    "a/b testing": {"analytics", "data analysis", "statistics"},
    "strategy": {"leadership", "product management"},
    "operations": {"project management", "analytics", "process improvement"},
    "ux": {"ui", "user research", "prototyping", "figma", "product design"},
    "ui": {"ux", "figma", "design", "prototyping"},
    "figma": {"ui", "ux", "design", "prototyping"},
    "design": {"ui", "ux", "figma", "graphic design"},
    "research": {"data analysis", "analytics", "ux", "user research"},
    "finance": {"accounting", "excel", "analytics"},
    "accounting": {"finance", "excel"},
    "hr": {"recruiting", "people operations"},
    "recruiting": {"hr", "people management"},
    "compliance": {"legal", "data protection"},
    "legal": {"compliance", "data protection"},
    "data protection": {"compliance", "security", "cybersecurity"},
    "testing": {"test automation", "pytest", "jest", "cypress", "playwright", "selenium", "tdd", "qa"},
    "test automation": {"selenium", "cypress", "playwright", "pytest", "jest", "testing", "tdd", "qa"},
    "tdd": {"testing", "test automation", "pytest", "jest", "cypress", "playwright"},
    "selenium": {"test automation", "cypress", "playwright", "testing", "qa"},
    "cypress": {"test automation", "playwright", "selenium", "testing", "qa"},
    "playwright": {"test automation", "cypress", "selenium", "testing", "qa"},
    "pytest": {"testing", "test automation", "jest", "python"},
    "jest": {"testing", "test automation", "pytest", "javascript", "typescript"},
    "qa": {"testing", "test automation", "selenium", "cypress", "playwright"},
    "system design": {"distributed systems", "microservices", "architecture"},
    "distributed systems": {"system design", "microservices", "kafka", "concurrency"},
    "mobile": {"android", "ios", "react native", "flutter", "kotlin", "swift"},
    "android": {"kotlin", "java", "flutter", "react native", "ios", "mobile"},
    "ios": {"swift", "objective-c", "react native", "flutter", "android", "mobile"},
    "objective-c": {"swift", "ios", "c"},
    "fullstack": {"react", "node.js", "python", "javascript", "typescript", "express", "django", "fastapi", "mongodb", "postgresql"},
    "backend": {"python", "java", "node.js", "go", "ruby", "php", "c#", "spring", "django", "fastapi", "express"},
    "frontend": {"react", "vue", "angular", "svelte", "next.js", "javascript", "typescript", "html", "css"},
}

#: Status -> evidence confidence multiplier (0-100) used for matchConfidence.
STATUS_CONFIDENCE = {
    "VERIFIED": 100,
    "USER_CONFIRMED": 95,
    "AI_EXTRACTED": 80,
    "INFERRED": 60,
    "UNKNOWN": 30,
    "REJECTED": 0,
}


def _canonical_from_aliases(text: str) -> str | None:
    """Return the canonical skill a requirement string refers to, or None."""
    lowered = text.strip().lower()
    if lowered in SKILL_ALIASES:
        return lowered
    for skill, aliases in SKILL_ALIASES.items():
        for alias in aliases:
            pattern = re.compile(rf"(?<![a-z0-9]){alias}(?![a-z0-9])")
            if pattern.search(lowered):
                return skill
    return None


def canonicalize_skill(text: str | None) -> str | None:
    """Canonical skill name for a fact/requirement, or None if not a known skill."""
    if not text:
        return None
    canon = _canonical_from_aliases(text)
    if canon is None:
        return None
    if canon in GENERIC_SKILLS:
        return None
    return canon


def _tokens(value: str) -> set[str]:
    return {t for t in re.split(r"[^a-z0-9+#.]+", value.lower()) if len(t) >= 3}


def _partial_overlap(a: str, b: str) -> bool:
    if not a or not b:
        return False
    shared = _tokens(a) & _tokens(b)
    if shared:
        return True
    na, nb = a.lower().strip(), b.lower().strip()
    return len(na) >= 4 and len(nb) >= 4 and (na in nb or nb in na)


def classify_requirement(
    requirement: str,
    profile_skills: list[str],
) -> tuple[str, str | None, int]:
    """Classify a requirement against the user's profile skills.

    Returns (classification, matched_profile_skill, skill_score).
    """
    req_skill = canonicalize_skill(requirement)
    for skill in profile_skills:
        if not skill:
            continue
        canon = canonicalize_skill(skill)
        if canon and req_skill and canon == req_skill:
            return DIRECT_MATCH, skill, 100
    if req_skill:
        for skill in profile_skills:
            canon = canonicalize_skill(skill)
            if canon and req_skill in RELATED_SKILLS.get(canon, set()):
                return RELATED_MATCH, skill, 70
    for skill in profile_skills:
        if _partial_overlap(req_skill or requirement, skill):
            return PARTIAL_MATCH, skill, 45
    return NO_EVIDENCE, None, 0


def skill_fact_type(skill: str) -> str:
    """Map a skill name to TECHNICAL_SKILL or SOFT_SKILL."""
    from app.db.models.career import CareerFactType

    if skill.strip().lower() in SOFT_SKILLS:
        return CareerFactType.SOFT_SKILL.value
    return CareerFactType.TECHNICAL_SKILL.value
