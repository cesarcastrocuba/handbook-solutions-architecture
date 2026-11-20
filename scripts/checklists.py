#!/usr/bin/env python3
"""Canonical architecture review checklists (Master Prompt §4.2–4.3).

`checklists/canonical/*.yaml` is the canonical source: one file per domain,
stable `SA-<DOMAIN>-NNN` identifiers independent of chapter numbering. The
review questions also appear in the manuscript; `--check` keeps both in step.

  --bootstrap  create missing domain files from the manuscript checklists
  --check      validate schema, identifiers, enrichment and manuscript parity
  --export     generate _build/checklists/exports/ (CSV, JSON, Markdown, assessment template)
"""
import argparse
import csv
import io
import json
from pathlib import Path
import re
import sys

import jsonschema
import yaml

ROOT = Path(__file__).resolve().parents[1]
CANONICAL = ROOT/'checklists/canonical'
EXPORTS = ROOT/'_build/checklists/exports'
SCHEMA = ROOT/'checklists/schema/review-checklist.schema.json'
RETIRED = ROOT/'checklists/retired-ids.txt'
SCHEMA_VERSION = '3.0.0'
ITEM = re.compile(r'^☐\s+(.*\S)\s*$')

# Domain code → manuscript file holding its checklist. Codes never change when chapters move.
DOMAINS = {
    'REQ': ('Requirements', 'chapters/ch01-architecture-requirements.qmd'),
    'PRI': ('Principles', 'chapters/ch02-architecture-principles.qmd'),
    'DEC': ('Decisions', 'chapters/ch03-architecture-decisions.qmd'),
    'GOV': ('Governance', 'chapters/ch04-architecture-governance.qmd'),
    'DATA': ('Data', 'chapters/ch05-data-architecture.qmd'),
    'INT': ('Integration', 'chapters/ch06-integration-architecture.qmd'),
    'APP': ('Application', 'chapters/ch07-application-architecture.qmd'),
    'INF': ('Infrastructure', 'chapters/ch08-infrastructure-and-cloud-architecture.qmd'),
    'PLAT': ('Platform', 'chapters/ch09-platform-architecture.qmd'),
    'SEC': ('Security', 'chapters/ch10-security-architecture.qmd'),
    'REL': ('Observability and reliability', 'chapters/ch11-observability-reliability-and-sre.qmd'),
    'OPS': ('Deployment and operations', 'chapters/ch12-deployment-and-operations.qmd'),
    'VAL': ('Architecture documentation', 'chapters/ch13-architecture-documentation.qmd'),
    'EVAL': ('Architecture evaluation', 'chapters/ch14-architecture-evaluation.qmd'),
    'TEST': ('Testing and quality verification', 'chapters/ch15-testing-and-quality-verification.qmd'),
    'EVO': ('Evolution and economics', 'chapters/ch16-architecture-evolution-and-economics.qmd'),
    'ART': ('Artifacts', 'chapters/ch17-software-engineering-and-architecture-artifacts.qmd'),
    'FWK': ('Frameworks, methods and standards', 'chapters/ch18-architecture-frameworks-methods-and-standards.qmd'),
    'AI': ('AI and machine learning', 'chapters/ch19-ai-and-machine-learning-architecture.qmd'),
    'ASR': ('Architecture assurance', 'appendices/appendix-c-architecture-assurance-checklist.qmd'),
}
ENRICHED = ('title', 'rationale', 'applicability', 'expected_evidence', 'risk_relevance')
COLUMNS = ['id', 'domain', 'title', 'question', 'rationale', 'applicability', 'expected_evidence',
           'section', 'external_reference', 'risk_relevance', 'version', 'status']
ASSESSMENT = ['id', 'domain', 'question', 'applicable', 'assessment_status', 'evidence_reference',
              'reviewer', 'review_date', 'findings', 'remediation_owner', 'due_date']


def manuscript_items(rel):
    """Ordered (question, group) pairs of the review checklist in one manuscript file."""
    path = ROOT/'manuscript'/rel
    if not path.exists():
        return None
    lines = path.read_text().splitlines()
    if rel.startswith('appendices/'):
        out, group = [], None
        for line in lines:
            if line.startswith('**') and line.endswith('**'):
                group = line.strip('*')
            elif (m := ITEM.match(line)):
                out.append((m[1], group))
        return out
    start = next(i for i, line in enumerate(lines)
                 if re.match(r'^:::\s+\{[^}]*\btitle="Architecture Review Checklist —[^"\n]+"[^}]*\}\s*$', line))
    out = []
    for line in lines[start+1:]:
        if line.startswith(':::'):
            break
        if (m := ITEM.match(line)):
            out.append((m[1], None))
    return out


def section_of(rel):
    number = re.match(r'(?:chapters/ch(\d+)|appendices/appendix-([a-j]))', rel)
    return number[1].lstrip('0') if number[1] else number[2].upper()


def load(code):
    path = CANONICAL/f'{code.lower()}.yaml'
    return yaml.safe_load(path.read_text()) if path.exists() else None


def bootstrap():
    CANONICAL.mkdir(parents=True, exist_ok=True)
    created = 0
    for code, (title, rel) in DOMAINS.items():
        items = manuscript_items(rel)
        if items is None or (CANONICAL/f'{code.lower()}.yaml').exists():
            continue
        data = {
            'schema_version': SCHEMA_VERSION, 'domain': f'SA-{code}', 'title': title, 'manuscript': rel,
            'items': [{
                'id': f'SA-{code}-{n:03d}', 'title': '', 'question': question, 'rationale': '', 'applicability': '',
                'expected_evidence': '', 'section': section_of(rel), 'external_reference': '',
                'risk_relevance': '', 'version': '2.1', 'status': 'active',
                **({'group': group} if group else {}),
            } for n, (question, group) in enumerate(items, 1)],
        }
        (CANONICAL/f'{code.lower()}.yaml').write_text(yaml.safe_dump(data, sort_keys=False, allow_unicode=True, width=1000))
        created += 1
    return created


def check(require_enriched=True):
    schema = json.loads(SCHEMA.read_text())
    validator = jsonschema.Draft202012Validator(schema)
    retired = set(RETIRED.read_text().split()) if RETIRED.exists() else set()
    errors, seen = [], set()
    files = {p.stem.upper() for p in CANONICAL.glob('*.yaml')}
    for code in sorted(files - set(DOMAINS)):
        errors.append(f'{code.lower()}.yaml: unknown domain')
    for code, (title, rel) in DOMAINS.items():
        data, items = load(code), manuscript_items(rel)
        if data is None:
            if items is not None:
                errors.append(f'{rel}: checklist has no canonical file {code.lower()}.yaml')
            continue
        errors += [f'{code.lower()}.yaml: {e.message}' for e in validator.iter_errors(data)]
        if data.get('domain') != f'SA-{code}' or data.get('manuscript') != rel:
            errors.append(f'{code.lower()}.yaml: domain/manuscript must be SA-{code} / {rel}')
        active = [i for i in data.get('items', []) if i.get('status') == 'active']
        for item in data.get('items', []):
            if item['id'] in seen:
                errors.append(f'{item["id"]}: duplicate identifier')
            if item['id'] in retired:
                errors.append(f'{item["id"]}: retired identifiers must not be reused')
            if not item['id'].startswith(f'SA-{code}-'):
                errors.append(f'{item["id"]}: identifier outside domain SA-{code}')
            seen.add(item['id'])
            if require_enriched and item.get('status') == 'active':
                errors += [f'{item["id"]}: {field} is empty' for field in ENRICHED if not str(item.get(field, '')).strip()]
        if items is None:
            errors.append(f'{rel}: manuscript file missing for {code.lower()}.yaml')
        elif [i['question'] for i in active] != [q for q, _ in items]:
            errors.append(f'{rel}: manuscript checklist and SA-{code} active questions differ in text or order')
    return errors


def rows():
    for code in DOMAINS:
        data = load(code)
        for item in (data or {}).get('items', []):
            if item['status'] == 'active':
                yield {**{c: item.get(c, '') for c in COLUMNS}, 'domain': data['title']}


def csv_text(records, columns):
    stream = io.StringIO()
    writer = csv.DictWriter(stream, fieldnames=columns, lineterminator='\n', extrasaction='ignore')
    writer.writeheader()
    writer.writerows(records)
    return stream.getvalue()


def export():
    EXPORTS.mkdir(parents=True, exist_ok=True)
    records = list(rows())
    outputs = {
        'architecture-review-checklist.csv': csv_text(records, COLUMNS),
        'architecture-review-checklist.json': json.dumps(records, ensure_ascii=False, indent=2)+'\n',
        # Assessment responses are kept apart from the definitions; outcomes start blank.
        'architecture-review-assessment-template.csv': csv_text([{k: r[k] for k in ('id', 'domain', 'question')} for r in records], ASSESSMENT),
    }
    md = ['# Architecture Review Checklist', '', 'Generated from `checklists/canonical/`. Do not edit by hand.', '']
    for code in DOMAINS:
        data = load(code)
        if not data:
            continue
        md += [f'## {data["title"]} (SA-{code})', '']
        md += [f'- **{i["id"]}** — {i["question"]}' for i in data['items'] if i['status'] == 'active']
        md.append('')
    outputs['architecture-review-checklist.md'] = '\n'.join(md)
    changed = 0
    for name, text in outputs.items():
        path = EXPORTS/name
        if not path.exists() or path.read_text() != text:
            path.write_text(text)
            changed += 1
    return changed, len(records)


def main():
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument('--bootstrap', action='store_true')
    parser.add_argument('--check', action='store_true')
    parser.add_argument('--export', action='store_true')
    parser.add_argument('--allow-unenriched', action='store_true', help='skip the enrichment check (authoring only)')
    args = parser.parse_args()
    if args.bootstrap:
        print(f'BOOTSTRAP: {bootstrap()} domain files created')
    if args.check:
        errors = check(require_enriched=not args.allow_unenriched)
        if errors:
            print('\n'.join(errors[:60]), file=sys.stderr)
            return 1
        print(f'CHECKLISTS_OK: {sum(1 for _ in rows())} active items in {len(list(CANONICAL.glob("*.yaml")))} domains')
    if args.export:
        changed, count = export()
        print(f'EXPORT_OK: {count} items, {changed} files updated')
    return 0


if __name__ == '__main__':
    sys.exit(main())
