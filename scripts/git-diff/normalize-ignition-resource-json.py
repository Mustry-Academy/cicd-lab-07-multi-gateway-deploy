#!/usr/bin/env python3
"""Normalize Ignition resource.json files for Git textconv diffs."""

import json
import sys
from pathlib import Path


def read_input(path_arg):
    if path_arg == "-":
        return sys.stdin.buffer.read()
    return Path(path_arg).read_bytes()


def normalize_resource_json(value):
    if not isinstance(value, dict):
        return value

    normalized = dict(value)
    attributes = normalized.get("attributes")
    if isinstance(attributes, dict):
        attributes = dict(attributes)
        attributes.pop("lastModificationSignature", None)

        last_modification = attributes.get("lastModification")
        if isinstance(last_modification, dict):
            last_modification = dict(last_modification)
            last_modification.pop("actor", None)
            last_modification.pop("timestamp", None)
            if last_modification:
                attributes["lastModification"] = last_modification
            else:
                attributes.pop("lastModification", None)

        normalized["attributes"] = attributes

    return normalized


def main(argv):
    if len(argv) != 2:
        print("usage: normalize-ignition-resource-json.py <path|->", file=sys.stderr)
        return 2

    raw = read_input(argv[1])
    try:
        text = raw.decode("utf-8")
        parsed = json.loads(text)
    except (UnicodeDecodeError, json.JSONDecodeError):
        sys.stdout.buffer.write(raw)
        return 0

    normalized = normalize_resource_json(parsed)
    json.dump(normalized, sys.stdout, indent=2, sort_keys=True, ensure_ascii=False)
    sys.stdout.write("\n")
    return 0


if __name__ == "__main__":
    raise SystemExit(main(sys.argv))
