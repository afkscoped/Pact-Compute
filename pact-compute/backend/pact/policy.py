import re
from datetime import datetime
from decimal import Decimal
from typing import Literal

from pydantic import BaseModel, Field


Kind = Literal['min_vram_mib', 'gpu_count', 'gpu_model', 'grid_zone', 'deadline_seconds',
               'deadline_utc', 'max_deferral_seconds', 'max_charge_cents', 'max_rate_cents',
               'carbon_limit_g', 'prefer_low_carbon', 'report_required']
NUMBER = r'(\d+(?:\.\d+)?)'
DURATION = NUMBER + r'\s*(seconds?|minutes?|hours?)'
PRICE = NUMBER + r'\s*(?:compute\s+)?credits?'
MODAL = r'(?:must\s+|shall\s+|should\s+)?'
SUBJECT = r'(?:(?:all\s+)?(?:jobs?|workloads?|tasks?)\s+)?'
EXAMPLE = (
    'Jobs require at least 4 GiB VRAM.\n'
    'Jobs must finish within 12 minutes.\n'
    'Total charge must not exceed 4 compute credits.\n'
    'Flexible jobs may be deferred by at most 3 minutes.\n'
    'Prefer lower-carbon execution.\n'
    'Energy reporting is required.'
)


class Rule(BaseModel):
    kind: Kind
    value: int | str | bool
    start: int | None = Field(default=None, ge=0)
    end: int | None = Field(default=None, ge=0)
    rationale: str | None = Field(default=None, max_length=500)
    strict: bool = False


class PolicyText(BaseModel):
    title: str = Field(min_length=2, max_length=120)
    source: str = Field(min_length=4, max_length=16000)
    method: Literal['local', 'llm'] = 'local'


class Revision(BaseModel):
    rules: list[Rule] = Field(min_length=1, max_length=30)
    resolutions: dict[str, str] = Field(default_factory=dict)


def seconds(value, unit):
    factor = {'second': 1, 'minute': 60, 'hour': 3600}[unit.lower().rstrip('s')]
    return int(Decimal(value) * factor)


def cents(value):
    scaled = Decimal(value) * 100
    if scaled != scaled.to_integral_value():
        raise ValueError('Use no more than two decimal places for credits.')
    return int(scaled)


def memory(value, unit):
    scale = {'mib': 1, 'gib': 1024, 'gb': Decimal(1000000000) / 1048576}[unit.lower()]
    return int((Decimal(value) * scale).to_integral_value(rounding='ROUND_CEILING'))


def utc(value):
    parsed = datetime.fromisoformat(value.replace('Z', '+00:00'))
    if parsed.tzinfo is None:
        raise ValueError('Include a timezone offset or Z.')
    return int(parsed.timestamp())


PATTERNS = [
    ('min_vram_mib', SUBJECT + r'(?:(?:must\s+)?(?:require|requires|need|needs|have)\s+)?(?:at\s+least|min(?:imum)?(?:\s+of)?)\s+' + NUMBER + r'\s*(mib|gib|gb)\s+(?:of\s+)?(?:gpu\s+memory|vram)', memory),
    ('gpu_count', SUBJECT + r'(?:must\s+)?(?:use|require|requires)\s+(\d+)\s+gpus?', int),
    ('gpu_model', SUBJECT + MODAL + r'(?:use|require)\s+(?:gpu\s+)?model\s+([A-Za-z0-9 ._-]{2,45})', str),
    ('grid_zone', SUBJECT + MODAL + r'(?:run|execute)\s+(?:only\s+)?in\s+(?:grid\s+)?(?:zone\s+)?([A-Za-z0-9_-]{2,20})', str.upper),
    ('deadline_seconds', SUBJECT + MODAL + r'(?:finish|complete)\s+within\s+' + DURATION + r'(?:\s+of\s+submission)?', seconds),
    ('deadline_utc', SUBJECT + MODAL + r'(?:finish|complete)\s+by\s+(\d{4}-\d{2}-\d{2}[T ]\d{2}:\d{2}(?::\d{2})?(?:Z|[+-]\d{2}:\d{2}))', utc),
    ('max_deferral_seconds', r'(?:flexible\s+)?(?:jobs?\s+)?(?:may|can)\s+(?:be\s+)?(?:deferred|delayed)\s+(?:by\s+)?(?:up\s+to|at\s+most)\s+' + DURATION, seconds),
    ('max_charge_cents', r'(?:max(?:imum)?(?:\s+total)?\s+(?:charge|cost)(?:\s+is)?|(?:total\s+)?(?:charge|cost)\s+(?:must\s+not\s+exceed|must\s+be\s+at\s+most|must\s+be\s+(?P<strict>under|below)))\s+' + PRICE,
     cents),
    ('max_rate_cents', r'(?:max(?:imum)?\s+rate(?:\s+is)?|rate\s+must\s+not\s+exceed)\s+' + PRICE + r'\s+per\s+gpu[- ]hour', cents),
    ('carbon_limit_g', r'(?:estimated\s+)?(?:emissions|carbon)\s+must\s+not\s+exceed\s+' + NUMBER + r'\s*(kg|g)\s*(?:co2|co₂)(?:\s+per\s+job)?',
     lambda value, unit: int(Decimal(value) * (1000 if unit.lower() == 'kg' else 1))),
    ('prefer_low_carbon', r'prefer\s+(?:lower|low)[ -]carbon\s+execution', lambda: True),
    ('report_required', r'(?:energy|gpu energy|telemetry)\s+reporting\s+is\s+required', lambda: True),
]

LIMITS = {
    'min_vram_mib': (1, 2_000_000), 'gpu_count': (1, 128),
    'deadline_seconds': (1, 30 * 86400), 'deadline_utc': (1, 4_102_444_800),
    'max_deferral_seconds': (0, 7 * 86400), 'max_charge_cents': (0, 100_000_000),
    'max_rate_cents': (0, 10_000_000), 'carbon_limit_g': (0, 1_000_000),
}


def issue(code, message, start=None, end=None):
    suffix = start if start is not None else 'general'
    return {'id': f'{code}:{suffix}',
            'code': code, 'message': message, 'start': start, 'end': end}


def parse_local(source: str):
    rules = []
    issues = []
    for match in re.finditer(r'[^;\n]+', source):
        for clause in re.finditer(r'.+?(?:[.!?](?=\s|$)|$)', match.group()):
            raw = clause.group()
            body = raw.strip().rstrip('.!?').rstrip()
            if not body:
                continue
            start = match.start() + clause.start() + len(raw) - len(raw.lstrip())
            end = start + len(body)
            for kind, pattern, normalize in PATTERNS:
                result = re.fullmatch(pattern, body, re.I)
                if result:
                    groups = result.groups()
                    strict = bool(result.groupdict().get('strict'))
                    values = groups[1:] if 'strict' in result.groupdict() else groups
                    try:
                        rules.append(Rule(kind=kind, value=normalize(*values), start=start, end=end, strict=strict))
                    except ValueError as exc:
                        issues.append(issue('invalid_value', str(exc), start, end))
                    break
            else:
                code = 'ambiguous_deadline' if re.search(r'\b(?:finish|complete)\s+by\b', body, re.I) else 'unsupported'
                message = ('Specify a full date, time and timezone, such as 2026-11-12T17:00:00+05:30.'
                           if code == 'ambiguous_deadline' else
                           'This wording needs a reviewer. Rewrite it as a supported rule or record its disposition.')
                issues.append(issue(code, message, start, end))
    return rules, issues


def verify(source: str, rules: list[Rule]):
    issues = []
    by_kind = {}
    if not rules:
        return [issue('empty', 'Add at least one supported rule.')]
    for rule in rules:
        if rule.kind in by_kind:
            issues.append(issue('duplicate_' + rule.kind, f'Combine duplicate {rule.kind} rules into one value.', rule.start, rule.end))
        by_kind[rule.kind] = rule
        if rule.kind in LIMITS:
            low, high = LIMITS[rule.kind]
            if type(rule.value) is not int or not low <= rule.value <= high:
                issues.append(issue('invalid_' + rule.kind, f'Expected an integer from {low} to {high}.', rule.start, rule.end))
        elif rule.kind in {'gpu_model', 'grid_zone'}:
            if type(rule.value) is not str or not rule.value.strip() or len(rule.value) > 60:
                issues.append(issue('invalid_' + rule.kind, 'Enter a nonempty model or grid zone.', rule.start, rule.end))
        elif rule.value is not True:
            issues.append(issue('invalid_' + rule.kind, 'Expected true for this clause.', rule.start, rule.end))
        if rule.strict and rule.kind not in {'max_charge_cents', 'max_rate_cents', 'carbon_limit_g'}:
            issues.append(issue('invalid_operator', 'This rule uses the default inclusive boundary.', rule.start, rule.end))
        if rule.start is None and rule.end is None:
            if not (rule.rationale or '').strip():
                issues.append(issue('missing_evidence_' + rule.kind, 'Provide a source span or an explicit reviewer rationale.'))
        elif rule.start is None or rule.end is None or not 0 <= rule.start < rule.end <= len(source):
            issues.append(issue('invalid_span', 'Evidence offsets are outside the contract.', rule.start, rule.end))
        else:
            extracted, _ = parse_local(source[rule.start:rule.end])
            supported = any(r.kind == rule.kind and r.value == rule.value and r.strict == rule.strict for r in extracted)
            if not supported and not (rule.rationale or '').strip():
                issues.append(issue('review_evidence_' + rule.kind, 'Confirm the normalized value and record a rationale.', rule.start, rule.end))
    return issues


def compile_local(source: str):
    rules, issues = parse_local(source)
    return rules, issues + verify(source, rules)


def values(rules):
    return {rule['kind']: rule['value'] for rule in rules}


def exceeds(rules, kind, value):
    for rule in rules:
        if rule['kind'] == kind:
            return value >= rule['value'] if rule['strict'] else value > rule['value']
    return False


def deadline(rules, submitted_at, fallback=900):
    limits = values(rules)
    deadlines = []
    if 'deadline_seconds' in limits:
        deadlines.append(submitted_at + limits['deadline_seconds'])
    if 'deadline_utc' in limits:
        deadlines.append(limits['deadline_utc'])
    return min(deadlines) if deadlines else submitted_at + fallback
