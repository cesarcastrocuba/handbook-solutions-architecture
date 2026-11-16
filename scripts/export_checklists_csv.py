#!/usr/bin/env python3
"""Validate/export checklist CSV: --all RC2 transcriptions or the enriched Chapter 6 pilot.

Implements Master Prompt Sections 4.2 and 4.3 (`AC-P1B-03`, `AC-P1B-05`) for the
Phase 1 Chapter 6 pilot (`checklists/data/ch06-integration-checklist.yaml` ->
`_build/checklists/exports/ch06-integration-checklist.csv`).
"""

from __future__ import annotations

import argparse
import csv
import io
import json
import re
import sys
from pathlib import Path
from typing import Any

CSV_COLUMNS = [
    "id",
    "chapter",
    "section",
    "domain",
    "question",
    "verification_method",
    "evidence_expected",
    "severity_if_missing",
    "mandatory_or_contextual",
    "tags",
    "version",
]


def parse_simple_checklist_yaml(yaml_text: str) -> dict[str, Any]:
    """Parse canonical checklist YAML using PyYAML if installed, with deterministic stdlib fallback."""
    try:
        import yaml  # type: ignore

        loaded = yaml.safe_load(yaml_text)
        if isinstance(loaded, dict):
            return loaded
    except Exception:
        pass

    result: dict[str, Any] = {}
    items: list[dict[str, Any]] = []
    current_item: dict[str, Any] | None = None
    in_tags = False

    def unquote(val: str) -> Any:
        val = val.strip()
        if (val.startswith('"') and val.endswith('"')) or (val.startswith("'") and val.endswith("'")):
            return val[1:-1]
        if val.isdigit():
            return int(val)
        return val

    for raw_line in yaml_text.splitlines():
        line = raw_line.rstrip()
        if not line or line.lstrip().startswith("#"):
            continue
        if not line.startswith(" "):
            key, _, rest = line.partition(":")
            key = key.strip()
            rest = rest.strip()
            if key == "items":
                result["items"] = items
            else:
                result[key] = unquote(rest)
            continue

        stripped = line.lstrip()
        indent = len(line) - len(stripped)
        if indent == 2 and stripped.startswith("- "):
            current_item = {}
            items.append(current_item)
            in_tags = False
            kv = stripped[2:].strip()
            if kv:
                k, _, v = kv.partition(":")
                current_item[k.strip()] = unquote(v)
        elif indent == 4 and current_item is not None:
            k, _, v = stripped.partition(":")
            k = k.strip()
            v = v.strip()
            if k == "tags":
                current_item["tags"] = []
                in_tags = True
            else:
                in_tags = False
                current_item[k] = unquote(v)
        elif indent == 6 and in_tags and current_item is not None and stripped.startswith("- "):
            current_item["tags"].append(unquote(stripped[2:]))

    return result


def validate_against_schema(data: dict[str, Any], schema: dict[str, Any]) -> list[str]:
    """Validate checklist data against `checklists/schema/checklist.schema.json`."""
    errors: list[str] = []

    try:
        import jsonschema  # type: ignore

        validator = jsonschema.Draft202012Validator(schema)
        for err in sorted(validator.iter_errors(data), key=lambda e: list(e.path)):
            loc = ".".join(str(p) for p in err.path) or "<root>"
            errors.append(f"{loc}: {err.message}")
        if errors:
            return errors
    except ImportError:
        pass

    # Deterministic stdlib enforcement of all schema constraints
    req_top = set(schema.get("required", []))
    missing_top = req_top - set(data.keys())
    if missing_top:
        errors.append(f"Missing top-level required fields: {sorted(missing_top)}")
    extra_top = set(data.keys()) - set(schema.get("properties", {}).keys())
    if extra_top:
        errors.append(f"Unexpected top-level fields: {sorted(extra_top)}")
    if data.get("schema_version") != "2.1.0":
        errors.append(f"schema_version must be '2.1.0', got {data.get('schema_version')!r}")
    chapter = data.get("chapter")
    if not isinstance(chapter, int) or not (1 <= chapter <= 16):
        errors.append(f"chapter must be integer 1..16, got {chapter!r}")

    items = data.get("items")
    if not isinstance(items, list) or len(items) < 1:
        errors.append("items must be a non-empty list")
        return errors

    item_schema = schema["properties"]["items"]["items"]
    req_item = set(item_schema["required"])
    allowed_item = set(item_schema["properties"].keys())
    seen_ids: set[str] = set()

    for idx, item in enumerate(items):
        prefix = f"items[{idx}]"
        if not isinstance(item, dict):
            errors.append(f"{prefix}: must be an object")
            continue
        missing = req_item - set(item.keys())
        if missing:
            errors.append(f"{prefix}: missing required fields {sorted(missing)}")
        extra = set(item.keys()) - allowed_item
        if extra:
            errors.append(f"{prefix}: unexpected fields {sorted(extra)}")

        item_id = str(item.get("id", ""))
        if not re.match(r"^CHK-CH[0-9]{2}-[0-9]{2}$", item_id):
            errors.append(f"{prefix}.id: invalid pattern {item_id!r}")
        if item_id in seen_ids:
            errors.append(f"{prefix}.id: duplicate id {item_id!r}")
        seen_ids.add(item_id)

        if item.get("chapter") != chapter:
            errors.append(f"{prefix}.chapter: expected {chapter}, got {item.get('chapter')!r}")
        if not re.match(r"^[0-9]+(\.[0-9]+)*$", str(item.get("section", ""))):
            errors.append(f"{prefix}.section: invalid section number {item.get('section')!r}")
        if len(str(item.get("question", ""))) < 10:
            errors.append(f"{prefix}.question: must be at least 10 characters")
        if item.get("severity_if_missing") not in ("Critical", "High", "Medium", "Low"):
            errors.append(f"{prefix}.severity_if_missing: invalid enum {item.get('severity_if_missing')!r}")
        if item.get("mandatory_or_contextual") not in ("Mandatory", "Contextual"):
            errors.append(
                f"{prefix}.mandatory_or_contextual: invalid enum {item.get('mandatory_or_contextual')!r}"
            )
        tags = item.get("tags")
        if not isinstance(tags, list) or len(tags) < 1 or not all(isinstance(t, str) and len(t) >= 2 for t in tags):
            errors.append(f"{prefix}.tags: must be a non-empty list of strings (minLength 2)")
        if item.get("version") not in ("2.0-RC2", "2.1"):
            errors.append(f"{prefix}.version: invalid version {item.get('version')!r}")

    return errors


def render_csv(data: dict[str, Any]) -> str:
    buf = io.StringIO()
    writer = csv.writer(buf, lineterminator="\n", quoting=csv.QUOTE_MINIMAL)
    writer.writerow(CSV_COLUMNS)
    for item in data["items"]:
        row = []
        for col in CSV_COLUMNS:
            val = item[col]
            if col == "tags" and isinstance(val, list):
                val = ";".join(val)
            row.append(val)
        writer.writerow(row)
    return buf.getvalue()


def run_self_test(schema_path: Path) -> int:
    schema = json.loads(schema_path.read_text(encoding="utf-8"))
    valid_payload = {
        "schema_version": "2.1.0",
        "chapter": 6,
        "chapter_title": "Integration Architecture",
        "checklist_title": "Review checklist — Integration",
        "source_ref": "src/06.md:179-184",
        "items": [
            {
                "id": "CHK-CH06-01",
                "chapter": 6,
                "section": "6.2.3",
                "domain": "Integration",
                "question": "Does every interface have named owners?",
                "verification_method": "Inspect ICD",
                "evidence_expected": "Signed ICD",
                "severity_if_missing": "High",
                "mandatory_or_contextual": "Mandatory",
                "tags": ["icd", "contracts"],
                "version": "2.0-RC2",
            }
        ],
    }
    assert validate_against_schema(valid_payload, schema) == []
    invalid_payload = dict(valid_payload, items=[dict(valid_payload["items"][0], severity_if_missing="Extreme")])
    errs = validate_against_schema(invalid_payload, schema)
    assert errs, "Self-test failed: invalid enum was not rejected"
    csv_text = render_csv(valid_payload)
    assert "CHK-CH06-01,6,6.2.3,Integration,Does every interface have named owners?" in csv_text
    print("SELF-TEST PASSED: export_checklists_csv.py")
    return 0


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--repo-root",
        type=Path,
        default=Path(__file__).resolve().parents[1],
        help="Path to repository root.",
    )
    parser.add_argument(
        "--self-test",
        action="store_true",
        help="Run built-in unit self-tests and exit.",
    )
    parser.add_argument("--all", action="store_true", help="Validate and export all RC2 checklist transcriptions.")
    parser.add_argument("--output-dir", type=Path, help="Generated export directory (default: _build/checklists/exports).")
    args = parser.parse_args()

    root = args.repo_root.resolve()
    schema_path = root / "checklists/schema/checklist.schema.json"
    if args.self_test:
        return run_self_test(schema_path)

    if args.all:
        # The frozen source transcriptions are data here; the legacy DOCX inventory
        # and normalization pipeline are deliberately not part of this book.
        try:
            import jsonschema
            source_schema = json.loads((root / "checklists/schema/checklist-source.schema.json").read_text())
            validator = jsonschema.Draft202012Validator(source_schema)
            records = []
            columns = ["id", "section", "group", "question", "source_id"]
            output = args.output_dir or root / "_build/checklists/exports"
            output.mkdir(parents=True, exist_ok=True)
            for path in sorted((root / "checklists/data").glob("*-source-checklist.yaml")):
                data = parse_simple_checklist_yaml(path.read_text())
                validator.validate(data)
                rows = data["items"]
                records.extend(rows)
                stream = io.StringIO()
                writer = csv.DictWriter(stream, fieldnames=columns, lineterminator="\n")
                writer.writeheader()
                writer.writerows(rows)
                (output / (path.stem + ".csv")).write_text(stream.getvalue())
            # The enriched chapter 6 pilot supersedes its source transcription.
            pilot = parse_simple_checklist_yaml((root / "checklists/data/ch06-integration-checklist.yaml").read_text())
            errors = validate_against_schema(pilot, json.loads(schema_path.read_text()))
            if errors:
                raise ValueError(str(errors))
            (output / "ch06-integration-checklist.csv").write_text(render_csv(pilot))
            # This frozen pilot records the DOCX title-and-question range. Its first
            # block is the title; the remaining blocks are the ordered questions.
            # Reject a changed range instead of guessing missing provenance.
            match = re.search(r"DOCX\[(\d+)\.\.(\d+)\]", pilot["source_ref"])
            if not match or int(match[2]) - int(match[1]) != len(pilot["items"]):
                raise ValueError("Chapter 6 source_ref must cover the title and every question")
            for offset, item in enumerate(pilot["items"], 1):
                records.append({
                    "id": item["id"],
                    "section": f"{pilot['chapter']}. {pilot['chapter_title']}",
                    "group": pilot["checklist_title"],
                    "question": item["question"],
                    "source_id": f"RC2-B{int(match[1]) + offset:04d}",
                })
            # Original reading order: numbered chapters, then Appendix C.
            records.sort(key=lambda row: int(m[1]) if (m := re.match(r"^(\d+)\.", row["section"])) else 999)
            stream = io.StringIO()
            writer = csv.DictWriter(stream, fieldnames=columns, lineterminator="\n")
            writer.writeheader()
            writer.writerows(records)
            (output / "all-checklists.csv").write_text(stream.getvalue())
            print(f"CHECKLIST_EXPORT_OK: items={len(records)} files={len(list((root / 'checklists/data').glob('*-source-checklist.yaml'))) + 2}")
            return 0
        except (ValueError, OSError, KeyError, TypeError, jsonschema.ValidationError) as exc:
            print(f"CHECKLIST_ERROR: {exc}", file=sys.stderr)
            return 1

    yaml_path = root / "checklists/data/ch06-integration-checklist.yaml"
    csv_path = (args.output_dir or root / "_build/checklists/exports") / "ch06-integration-checklist.csv"

    schema = json.loads(schema_path.read_text(encoding="utf-8"))
    data = parse_simple_checklist_yaml(yaml_path.read_text(encoding="utf-8"))
    errors = validate_against_schema(data, schema)
    if errors:
        for e in errors:
            print(f"SCHEMA_ERROR: {e}", file=sys.stderr)
        return 1

    csv_content = render_csv(data)
    csv_path.parent.mkdir(parents=True, exist_ok=True)
    if not csv_path.exists() or csv_path.read_text(encoding="utf-8") != csv_content:
        csv_path.write_text(csv_content, encoding="utf-8")

    print(
        f"CHECKLIST_EXPORT_OK: chapter={data['chapter']} items={len(data['items'])} "
        f"csv={csv_path}"
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
