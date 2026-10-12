"""Build exact catalog coverage. Pending records never count as reviewed."""

import argparse
from collections import Counter
import json
from pathlib import Path
import sys


ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
from component.pc.catalog import load_catalog


def validate_resource(item, valid_owners):
    for field in ("id", "owners", "name", "minimum_level", "kind", "capacity", "consumption", "recovery", "implementation"):
        if field not in item:
            raise ValueError(f"Missing resource field {field}: {item.get('id', '<unnamed>')}")
    owners = item["owners"]
    if not isinstance(owners, list) or not owners or set(owners) - valid_owners:
        raise ValueError(f"Invalid resource owners: {item['id']}")
    level = item["minimum_level"]
    if type(level) is not int or not 1 <= level <= 20:
        raise ValueError(f"Invalid resource minimum level: {item['id']}")
    capacity = item["capacity"]
    unlimited_target = capacity is None and "target" in item["kind"]
    valid_capacity = (isinstance(capacity, dict) and bool(capacity)
                      or isinstance(capacity, str) and bool(capacity.strip())
                      or type(capacity) is int and capacity > 0)
    if not (unlimited_target or valid_capacity):
        raise ValueError(f"Invalid resource capacity: {item['id']}")
    if not isinstance(item["recovery"], dict) or not item["recovery"]:
        raise ValueError(f"Invalid resource recovery: {item['id']}")
    if not item["consumption"]:
        raise ValueError(f"Empty resource consumption: {item['id']}")


def build_coverage():
    folder = ROOT / "data" / "dnd"
    review_data = json.loads((folder / "subclass-resource-reviews.json").read_text())
    reviews = review_data["reviews"]
    _, catalog = load_catalog()
    valid_owners = {entry.id for entry in catalog} | {entry.class_id for entry in catalog}
    resource_files = {}
    resource_ids = set()
    for path in sorted(folder.glob("resource-research-*.json")):
        supplement = json.loads(path.read_text())
        definitions = {}
        for item in supplement["entries"]:
            validate_resource(item, valid_owners)
            if item["id"] in resource_ids:
                raise ValueError(f"Duplicate resource: {item['id']}")
            resource_ids.add(item["id"])
            definitions[item["id"]] = item
        resource_files[path.name] = definitions
        for subclass_id, row in supplement.get("reviews", {}).items():
            if subclass_id in reviews:
                raise ValueError(f"Duplicate review: {subclass_id}")
            reviews[subclass_id] = {"status": "reviewed", "evidence": supplement["verification"],
                                     "source_url": supplement["source_root"] + row["page"],
                                     "resource_file": path.name, "implementation_complete": False,
                                     **{key: value for key, value in row.items() if key != "page"}}
    ids = {entry.id for entry in catalog}
    unknown = set(reviews) - ids
    if unknown:
        raise ValueError(f"Unknown reviewed subclasses: {sorted(unknown)}")
    records = []
    for entry in catalog:
        review = reviews.get(entry.id)
        row = {"id": entry.id, "name": entry.name, "class_id": entry.class_id,
               "source": entry.source, "status": "pending", "implementation_complete": False}
        if review:
            if review["status"] not in {"pending", "reviewed"}:
                raise ValueError(f"Invalid status: {entry.id}")
            if review["status"] == "reviewed":
                for field in ("evidence", "source_url", "resources", "shared_resources", "without_independent_resources"):
                    if field not in review:
                        raise ValueError(f"Missing {field}: {entry.id}")
                if review["evidence"] not in {"translation_checked", "official_checked"}:
                    raise ValueError(f"Unverified evidence: {entry.id}")
                resources = review["resources"]
                if resources:
                    definitions = resource_files[review["resource_file"]]
                    for resource in resources:
                        if resource not in definitions or entry.id not in definitions[resource]["owners"]:
                            raise ValueError(f"Missing or mismatched resource: {entry.id}: {resource}")
                if not resources and not (review["shared_resources"] or review["without_independent_resources"]):
                    raise ValueError(f"Empty review: {entry.id}")
            row.update(review)
        records.append(row)
    counts = Counter(row["status"] for row in records)
    return {"schema_version": 1, "scope": review_data["scope"],
            "reviewed_on": review_data["reviewed_on"], "complete": counts["pending"] == 0,
            "counts": {"total": len(records), "reviewed": counts["reviewed"], "pending": counts["pending"]},
            "books": dict(Counter(row["source"] for row in records)), "subclasses": records}


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--require-complete", action="store_true")
    parser.add_argument("--write", action="store_true")
    args = parser.parse_args()
    result = build_coverage()
    if args.write:
        output = ROOT / "data" / "dnd" / "subclass-resource-coverage.json"
        output.write_text(json.dumps(result, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    print(json.dumps(result["counts"], ensure_ascii=False))
    if args.require_complete and not result["complete"]:
        raise SystemExit(1)


if __name__ == "__main__":
    main()
