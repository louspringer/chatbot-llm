#!/usr/bin/env python3  # noqa: EXE001
# Ontology: tools:RuffCheck
# Implements: tools:LintingFramework
# Requirement: REQ-TOOLS-001 Code Linting
# Guidance: guidance:TestingPattern#CodeLinting
# Description: Tool for running Ruff linter with project-specific configuration
#   and ontology-based rule validation. Enhances Ruff with ontology framework
#   integration, custom RDF rules, and traceability support.

"""
Ontology-aware Ruff code quality checker.

This script enhances Ruff's capabilities by:
1. Integrating with the project's ontology framework
2. Providing custom rules for RDF/ontology code
3. Generating reports that link to requirements
4. Supporting traceability between code and ontologies
"""

import argparse
import subprocess
import sys
from pathlib import Path
from typing import Dict, List, NoReturn  # noqa: UP035

import rdflib as rdf
from rich.console import Console
from rich.table import Table

# Initialize rich console
console = Console()


class RuffOntologyChecker:
    """Ontology-aware code quality checker using Ruff."""

    def __init__(self, workspace_root: Path | None = None) -> None:
        """Initialize the checker with workspace configuration.

        Args:
            workspace_root: Root directory of the project workspace
        """
        self.workspace_root = workspace_root or Path.cwd()
        self.graph = rdf.Graph()
        self._load_ontologies()

    def _load_ontologies(self) -> None:
        """Load relevant ontologies for code quality checking."""
        ontology_files = [
            "guidance.ttl",
            "package_management.ttl",
            "traceability.ttl",
        ]

        for ontology in ontology_files:
            path = self.workspace_root / ontology
            if path.exists():
                self.graph.parse(path, format="turtle")

    def _get_quality_rules(self) -> List[Dict]:  # noqa
        """Extract code quality rules from ontologies.

        Returns:
            List of rule dictionaries with settings
        """
        query = """
        PREFIX quality: <./package_management.ttl#>
        PREFIX rdfs: <http://www.w3.org/2000/01/rdf-schema#>
        SELECT ?rule ?description ?severity ?autofix
        WHERE {
            ?rule a quality:CodeQualityRule ;
                  rdfs:comment ?description .
            OPTIONAL { ?rule quality:severity ?severity }
            OPTIONAL { ?rule quality:canAutofix ?autofix }
        }
        """

        results = self.graph.query(query)
        # rdflib's SPARQL results have dynamic attributes
        return [  # type: ignore[attr-defined]
            {
                "rule": str(row.rule),  # type: ignore[attr-defined]
                "description": (  # Break long line
                    str(row.description)  # type: ignore[attr-defined]
                ),
                "severity": (
                    str(row.severity)  # type: ignore[attr-defined]
                    if row.severity  # type: ignore[attr-defined]
                    else "warning"
                ),
                "autofix": (
                    bool(row.autofix)  # type: ignore[attr-defined]
                    if row.autofix  # type: ignore[attr-defined]
                    else False
                ),
            }
            for row in results
        ]

    def run_check(
        self,
        paths: list[str],
        *,
        autofix: bool = False,
    ) -> tuple[int, list[dict]]:
        """Run Ruff checks on specified paths.

        Args:
            paths: List of paths to check
            autofix: Whether to apply auto-fixes

        Returns:
            Tuple of (exit_code, list of violations)
        """
        cmd = ["ruff", "check"]
        if autofix:
            cmd.append("--fix")

        cmd.extend(paths)

        try:
            # Using a trusted command list, so subprocess is safe
            result = subprocess.run(  # noqa: S603
                cmd,
                capture_output=True,
                text=True,
                check=False,
            )
            violations = self._parse_violations(result.stdout)
            return result.returncode, violations
        except subprocess.CalledProcessError as e:
            console.print(f"[red]Error running Ruff: {e}[/red]")
            return 1, []

    def _parse_violations(self, output: str) -> list[dict]:
        """Parse Ruff output into structured violations.

        Args:
            output: Raw Ruff output string

        Returns:
            List of violation dictionaries
        """
        violations = []
        for line in output.splitlines():
            if not line or line.startswith(("Found", "Fixed")):
                continue

            try:
                file_path, line_no, char_no, message = line.split(":", 3)
                violations.append(
                    {
                        "file": file_path.strip(),
                        "line": int(line_no),
                        "char": int(char_no),
                        "message": message.strip(),
                    },
                )
            except ValueError:
                continue

        return violations

    def generate_report(self, violations: list[dict]) -> None:
        """Generate a rich formatted report of violations.

        Args:
            violations: List of violation dictionaries
        """
        table = Table(title="Code Quality Report")
        table.add_column("File", style="cyan")
        table.add_column("Line", justify="right", style="green")
        table.add_column("Char", justify="right", style="green")
        table.add_column("Message", style="yellow")
        table.add_column("Rule", style="magenta")

        for v in violations:
            rule = v["message"].split()[0] if v["message"] else "Unknown"
            table.add_row(
                str(v["file"]),
                str(v["line"]),
                str(v["char"]),
                v["message"],
                rule,
            )

        console.print(table)

    def check_ontology_compliance(self, violations: list[dict]) -> bool:
        """Check if violations comply with ontology rules.

        Args:
            violations: List of violation dictionaries

        Returns:
            True if compliant, False otherwise
        """
        rules = self._get_quality_rules()
        rule_ids = {r["rule"] for r in rules}

        for violation in violations:
            rule = violation["message"].split()[0]
            if rule not in rule_ids:
                msg = f"[yellow]Warning: Rule {rule} not defined in ontology[/yellow]"
                console.print(msg)
                return False

        return True


def main() -> NoReturn:
    """Main entry point for the script."""
    parser = argparse.ArgumentParser(
        description=("Ontology-aware Ruff code quality checker"),
    )
    parser.add_argument(
        "paths",
        nargs="*",
        default=["."],
        help="Paths to check (default: current directory)",
    )
    parser.add_argument(
        "--fix",
        action="store_true",
        help="Apply auto-fixes for supported rules",
    )
    parser.add_argument(
        "--workspace",
        type=Path,
        help="Path to workspace root (default: current directory)",
    )

    args = parser.parse_args()

    checker = RuffOntologyChecker(args.workspace)
    exit_code, violations = checker.run_check(args.paths, autofix=args.fix)

    if violations:
        checker.generate_report(violations)
        is_compliant = checker.check_ontology_compliance(violations)
        if not is_compliant:
            msg = "[red]❌ Found violations not defined in ontology[/red]"
            console.print(msg)
            exit_code = 1
    else:
        console.print("[green]✓ No violations found[/green]")

    sys.exit(exit_code)


if __name__ == "__main__":
    main()
