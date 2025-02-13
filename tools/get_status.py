#!/usr/bin/env python3
"""
Command-line tool to get comprehensive project status from ontology files.
"""

import argparse
from pathlib import Path

from jena_tools import JenaTools


def parse_args():
    parser = argparse.ArgumentParser(
        description="Get project status from ontology files"
    )
    parser.add_argument(
        "--files",
        nargs="+",
        help=(
            "List of TTL files to query "
            "(default: session.ttl deployment.ttl)"
        ),
        default=["session.ttl", "deployment.ttl"],
    )
    parser.add_argument(
        "--json", action="store_true", help="Output in JSON format"
    )
    return parser.parse_args()


def main():
    args = parse_args()

    # Initialize JenaTools
    jena = JenaTools()

    # Get status from specified files
    try:
        status = jena.get_status(args.files)

        if args.json:
            import json

            print(json.dumps(status, indent=2))
        else:
            print(jena.format_status_output(status))

    except Exception as e:
        print(f"Error getting status: {e}")
        return 1

    return 0


if __name__ == "__main__":
    exit(main())
