"""Pre-built prompt templates for common tasks."""
from __future__ import annotations

from dataclasses import dataclass
from typing import Optional


@dataclass
class PromptTemplate:
    """A pre-built prompt template."""

    id: str
    name: str
    description: str
    category: str
    target: str  # chatgpt or claude_code
    task: str
    context: str
    constraints: str
    deliverables: str
    tone: str
    tags: list[str]
    difficulty: str  # beginner, intermediate, advanced


# Security & Penetration Testing Templates
SECURITY_TEMPLATES = [
    PromptTemplate(
        id="sec-threat-model",
        name="Threat Modeling Assessment",
        description="Generate comprehensive threat models for applications",
        category="Security",
        target="chatgpt",
        task="Create a detailed threat model for the application",
        context="Application architecture, tech stack, data flows, user roles",
        constraints="Follow STRIDE methodology, identify attack vectors, assess impact and likelihood",
        deliverables="Threat model diagram, ranked threat list, mitigation recommendations, security controls",
        tone="analytical and thorough",
        tags=["security", "threat-modeling", "assessment"],
        difficulty="advanced",
    ),
    PromptTemplate(
        id="sec-code-audit",
        name="Security Code Audit",
        description="Perform security-focused code review",
        category="Security",
        target="claude_code",
        task="Conduct a security audit of the codebase looking for vulnerabilities",
        context="Codebase language, framework, authentication method, data handling practices",
        constraints="Check for OWASP Top 10, SQL injection, XSS, CSRF, insecure deserialization, secrets in code",
        deliverables="Vulnerability report with severity ratings, proof-of-concept exploits, remediation steps",
        tone="precise and security-focused",
        tags=["security", "code-review", "vulnerabilities"],
        difficulty="advanced",
    ),
    PromptTemplate(
        id="sec-penetration-test",
        name="Penetration Testing Plan",
        description="Design a penetration testing strategy",
        category="Security",
        target="chatgpt",
        task="Design a comprehensive penetration testing plan",
        context="Target system description, scope boundaries, rules of engagement, testing timeframe",
        constraints="Include reconnaissance, scanning, exploitation, privilege escalation, and persistence phases",
        deliverables="Testing methodology, tool recommendations, timeline, expected deliverables, reporting format",
        tone="methodical and professional",
        tags=["security", "pentest", "planning"],
        difficulty="advanced",
    ),
    PromptTemplate(
        id="sec-incident-response",
        name="Incident Response Playbook",
        description="Create incident response procedures",
        category="Security",
        target="chatgpt",
        task="Develop an incident response playbook",
        context="Organization type, assets, threat landscape, team structure, tools available",
        constraints="Cover detection, analysis, containment, eradication, recovery, and lessons learned",
        deliverables="Step-by-step playbook, communication templates, escalation matrix, forensics checklist",
        tone="clear and actionable",
        tags=["security", "incident-response", "playbook"],
        difficulty="intermediate",
    ),
]

# Development & Architecture Templates
DEVELOPMENT_TEMPLATES = [
    PromptTemplate(
        id="dev-architecture-design",
        name="System Architecture Design",
        description="Design scalable system architecture",
        category="Development",
        target="chatgpt",
        task="Design a scalable system architecture",
        context="Requirements, expected scale, performance targets, budget constraints, team expertise",
        constraints="Consider scalability, reliability, maintainability, cost-effectiveness",
        deliverables="Architecture diagram, technology stack recommendations, data flow, deployment strategy",
        tone="technical and comprehensive",
        tags=["architecture", "design", "scalability"],
        difficulty="advanced",
    ),
    PromptTemplate(
        id="dev-api-design",
        name="RESTful API Design",
        description="Design RESTful API endpoints",
        category="Development",
        target="claude_code",
        task="Design RESTful API endpoints for the application",
        context="Data models, business logic, authentication requirements, expected clients",
        constraints="Follow REST principles, include versioning, proper HTTP methods, pagination, error handling",
        deliverables="OpenAPI specification, endpoint documentation, authentication flow, error responses",
        tone="precise and standards-compliant",
        tags=["api", "rest", "design"],
        difficulty="intermediate",
    ),
    PromptTemplate(
        id="dev-database-schema",
        name="Database Schema Design",
        description="Design optimized database schema",
        category="Development",
        target="claude_code",
        task="Design an optimized database schema",
        context="Data requirements, relationships, query patterns, expected volume",
        constraints="Normalize to 3NF, add proper indexes, consider foreign keys, plan for migrations",
        deliverables="ERD diagram, SQL schema, index strategy, migration plan",
        tone="technical and detailed",
        tags=["database", "schema", "design"],
        difficulty="intermediate",
    ),
    PromptTemplate(
        id="dev-microservices",
        name="Microservices Architecture",
        description="Design microservices-based system",
        category="Development",
        target="chatgpt",
        task="Design a microservices architecture for the system",
        context="Monolith description, pain points, team structure, deployment capabilities",
        constraints="Define service boundaries, communication patterns, data consistency, deployment strategy",
        deliverables="Service map, API contracts, event schemas, deployment diagram, migration roadmap",
        tone="architectural and strategic",
        tags=["microservices", "architecture", "migration"],
        difficulty="advanced",
    ),
]

# DevOps & Infrastructure Templates
DEVOPS_TEMPLATES = [
    PromptTemplate(
        id="devops-cicd-pipeline",
        name="CI/CD Pipeline Setup",
        description="Design continuous integration and deployment pipeline",
        category="DevOps",
        target="claude_code",
        task="Design and implement a CI/CD pipeline",
        context="Tech stack, deployment targets, testing requirements, team workflow",
        constraints="Include build, test, security scanning, deployment stages; support rollbacks",
        deliverables="Pipeline configuration, stage definitions, deployment scripts, rollback procedures",
        tone="practical and automated",
        tags=["cicd", "devops", "automation"],
        difficulty="intermediate",
    ),
    PromptTemplate(
        id="devops-k8s-deployment",
        name="Kubernetes Deployment",
        description="Create Kubernetes deployment manifests",
        category="DevOps",
        target="claude_code",
        task="Create Kubernetes deployment manifests for the application",
        context="Application architecture, resource requirements, scaling needs, environments",
        constraints="Include deployments, services, ingress, configmaps, secrets, HPA",
        deliverables="K8s YAML manifests, namespace setup, resource limits, health checks",
        tone="infrastructure-focused",
        tags=["kubernetes", "k8s", "deployment"],
        difficulty="advanced",
    ),
    PromptTemplate(
        id="devops-monitoring",
        name="Monitoring & Alerting Setup",
        description="Design monitoring and alerting strategy",
        category="DevOps",
        target="chatgpt",
        task="Design a comprehensive monitoring and alerting strategy",
        context="System architecture, SLAs, on-call team, existing tools",
        constraints="Cover metrics, logs, traces; define SLIs, SLOs, error budgets",
        deliverables="Monitoring dashboard configs, alert rules, runbooks, escalation policies",
        tone="operational and proactive",
        tags=["monitoring", "alerting", "observability"],
        difficulty="intermediate",
    ),
]

# Code Review & Refactoring Templates
CODE_QUALITY_TEMPLATES = [
    PromptTemplate(
        id="code-review",
        name="Code Review Checklist",
        description="Perform thorough code review",
        category="Code Quality",
        target="claude_code",
        task="Review this code for quality, performance, and maintainability",
        context="Programming language, framework, project conventions, team standards",
        constraints="Check correctness, readability, performance, security, test coverage, documentation",
        deliverables="Review comments, severity ratings, refactoring suggestions, approval decision",
        tone="constructive and educational",
        tags=["code-review", "quality", "standards"],
        difficulty="intermediate",
    ),
    PromptTemplate(
        id="code-refactor",
        name="Code Refactoring Plan",
        description="Plan major code refactoring",
        category="Code Quality",
        target="claude_code",
        task="Plan a refactoring strategy for the legacy codebase",
        context="Current codebase state, pain points, business constraints, team capacity",
        constraints="Minimize risk, maintain backward compatibility, incremental approach",
        deliverables="Refactoring roadmap, step-by-step plan, testing strategy, rollback points",
        tone="strategic and risk-aware",
        tags=["refactoring", "legacy", "modernization"],
        difficulty="advanced",
    ),
    PromptTemplate(
        id="code-performance",
        name="Performance Optimization",
        description="Optimize code performance",
        category="Code Quality",
        target="claude_code",
        task="Analyze and optimize code for performance",
        context="Performance metrics, bottlenecks identified, constraints, acceptable tradeoffs",
        constraints="Profile first, optimize algorithmically, then implementation; maintain readability",
        deliverables="Optimization recommendations, benchmarks, code changes, performance comparison",
        tone="analytical and data-driven",
        tags=["performance", "optimization", "profiling"],
        difficulty="advanced",
    ),
]

# Testing Templates
TESTING_TEMPLATES = [
    PromptTemplate(
        id="test-strategy",
        name="Test Strategy Design",
        description="Create comprehensive testing strategy",
        category="Testing",
        target="chatgpt",
        task="Design a comprehensive testing strategy",
        context="Application type, tech stack, team size, release frequency, risk tolerance",
        constraints="Cover unit, integration, E2E, performance, security testing; define coverage targets",
        deliverables="Test strategy document, framework recommendations, automation plan, metrics",
        tone="systematic and thorough",
        tags=["testing", "strategy", "quality"],
        difficulty="intermediate",
    ),
    PromptTemplate(
        id="test-cases",
        name="Test Case Generation",
        description="Generate comprehensive test cases",
        category="Testing",
        target="claude_code",
        task="Generate test cases for the feature",
        context="Feature description, requirements, edge cases, data validation rules",
        constraints="Cover happy path, edge cases, error conditions, boundary values",
        deliverables="Test case list with inputs/expected outputs, priority levels, automation candidates",
        tone="detailed and exhaustive",
        tags=["testing", "test-cases", "qa"],
        difficulty="intermediate",
    ),
]

# Documentation Templates
DOCUMENTATION_TEMPLATES = [
    PromptTemplate(
        id="doc-api-docs",
        name="API Documentation",
        description="Create comprehensive API documentation",
        category="Documentation",
        target="claude_code",
        task="Create comprehensive API documentation",
        context="API endpoints, authentication, data models, error codes",
        constraints="Include examples, error handling, rate limits, versioning",
        deliverables="OpenAPI spec, endpoint descriptions, examples, authentication guide",
        tone="clear and developer-friendly",
        tags=["documentation", "api", "openapi"],
        difficulty="beginner",
    ),
    PromptTemplate(
        id="doc-readme",
        name="README Generation",
        description="Create project README",
        category="Documentation",
        target="claude_code",
        task="Create a comprehensive README for the project",
        context="Project purpose, tech stack, setup requirements, target audience",
        constraints="Include installation, usage, examples, contributing guidelines, license",
        deliverables="Complete README.md with badges, screenshots, code examples",
        tone="welcoming and informative",
        tags=["documentation", "readme", "onboarding"],
        difficulty="beginner",
    ),
]

# Combine all templates
ALL_TEMPLATES = (
    SECURITY_TEMPLATES
    + DEVELOPMENT_TEMPLATES
    + DEVOPS_TEMPLATES
    + CODE_QUALITY_TEMPLATES
    + TESTING_TEMPLATES
    + DOCUMENTATION_TEMPLATES
)


def get_all_templates() -> list[PromptTemplate]:
    """Get all available templates."""
    return ALL_TEMPLATES


def get_template_by_id(template_id: str) -> Optional[PromptTemplate]:
    """Get template by ID."""
    for template in ALL_TEMPLATES:
        if template.id == template_id:
            return template
    return None


def get_templates_by_category(category: str) -> list[PromptTemplate]:
    """Get templates by category."""
    return [t for t in ALL_TEMPLATES if t.category.lower() == category.lower()]


def get_templates_by_tag(tag: str) -> list[PromptTemplate]:
    """Get templates by tag."""
    return [t for t in ALL_TEMPLATES if tag.lower() in [t.lower() for t in t.tags]]


def get_templates_by_difficulty(difficulty: str) -> list[PromptTemplate]:
    """Get templates by difficulty level."""
    return [t for t in ALL_TEMPLATES if t.difficulty.lower() == difficulty.lower()]


def get_all_categories() -> list[str]:
    """Get all unique categories."""
    return sorted(list(set(t.category for t in ALL_TEMPLATES)))


def get_all_tags() -> list[str]:
    """Get all unique tags."""
    tags = set()
    for template in ALL_TEMPLATES:
        tags.update(template.tags)
    return sorted(list(tags))


def search_templates(query: str) -> list[PromptTemplate]:
    """Search templates by name, description, or tags."""
    query_lower = query.lower()
    results = []

    for template in ALL_TEMPLATES:
        if (
            query_lower in template.name.lower()
            or query_lower in template.description.lower()
            or any(query_lower in tag.lower() for tag in template.tags)
        ):
            results.append(template)

    return results
