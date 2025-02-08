#!/usr/bin/env python3

"""
Ontology and Session State Validator

Validates:
1. Ontology file consistency
2. Session state alignment with git history
3. Cross-references between ontologies
4. Semantic versioning compliance
5. Required metadata presence
"""

import logging
import subprocess
from pathlib import Path
from typing import Dict, List, Set, Tuple, Optional
from dataclasses import dataclass
import re
from datetime import datetime

from rdflib import Graph, Namespace, URIRef, Literal
from rdflib.namespace import RDF, RDFS, OWL, XSD


@dataclass
class OntologyState:
    file_path: Path
    version: str
    imports: Set[str]
    last_modified: datetime
    commit_hash: str
    dependencies: Set[str]


@dataclass
class ValidationIssue:
    severity: str  # 'ERROR', 'WARNING', 'INFO'
    message: str
    file: str
    details: Optional[str] = None


class OntologyValidator:
    def __init__(self, workspace_root: Path):
        self.workspace_root = workspace_root
        self.setup_logging()
        self.issues: List[ValidationIssue] = []

    def setup_logging(self):
        """Configure logging for the validator"""
        logging.basicConfig(
            level=logging.INFO, format="%(asctime)s - %(levelname)s - %(message)s"
        )
        self.logger = logging.getLogger(__name__)

    def get_git_state(self, file_path: Path) -> Tuple[str, datetime]:
        """Get git commit hash and last modified time for a file."""
        try:
            result = subprocess.run(
                ["git", "log", "-1", "--format=%H %aI", "--", file_path],
                capture_output=True,
                text=True,
                check=True,
            )
            commit_hash, date_str = result.stdout.strip().split()
            return commit_hash, datetime.fromisoformat(date_str)
        except subprocess.CalledProcessError:
            return "", datetime.now()

    def extract_version(self, graph: Graph, ontology_uri: URIRef) -> str:
        """Extract version information from ontology."""
        for _, _, version in graph.triples((ontology_uri, OWL.versionInfo, None)):
            return str(version)
        return "0.0.0"

    def validate_semantic_version(self, version: str) -> bool:
        """Validate semantic version format."""
        pattern = r"^\d+\.\d+\.\d+$"
        return bool(re.match(pattern, version))

    def extract_imports(self, graph: Graph) -> Set[str]:
        """Extract imported ontologies."""
        imports = set()
        for _, _, imp in graph.triples((None, OWL.imports, None)):
            imports.add(str(imp))
        return imports

    def get_ontology_state(self, file_path: Path) -> Optional[OntologyState]:
        """Get current state of an ontology file."""
        if not file_path.exists():
            return None

        try:
            graph = Graph()
            graph.parse(file_path, format="turtle")

            # Get ontology URI
            ontology_uri = None
            for s, p, o in graph.triples((None, RDF.type, OWL.Ontology)):
                ontology_uri = s
                break

            if not ontology_uri:
                self.issues.append(
                    ValidationIssue(
                        "ERROR", "No ontology declaration found", str(file_path)
                    )
                )
                return None

            # Get git state
            commit_hash, last_modified = self.get_git_state(file_path)

            # Get version
            version = self.extract_version(graph, ontology_uri)
            if not self.validate_semantic_version(version):
                self.issues.append(
                    ValidationIssue(
                        "ERROR",
                        "Invalid semantic version",
                        str(file_path),
                        f'Version "{version}" does not follow semantic versioning',
                    )
                )

            # Get imports
            imports = self.extract_imports(graph)

            # Get dependencies from triples
            dependencies = set()
            for s, p, o in graph:
                if isinstance(o, URIRef) and "#" in str(o):
                    dep = str(o).split("#")[0]
                    if dep.startswith("./"):
                        dependencies.add(dep[2:])

            return OntologyState(
                file_path=file_path,
                version=version,
                imports=imports,
                last_modified=last_modified,
                commit_hash=commit_hash,
                dependencies=dependencies,
            )

        except Exception as e:
            self.issues.append(
                ValidationIssue(
                    "ERROR", "Failed to parse ontology", str(file_path), str(e)
                )
            )
            return None

    def validate_cross_references(self, states: Dict[Path, OntologyState]):
        """Validate cross-references between ontologies."""
        for file_path, state in states.items():
            for dep in state.dependencies:
                dep_path = self.workspace_root / f"{dep}.ttl"
                if not dep_path.exists():
                    self.issues.append(
                        ValidationIssue(
                            "ERROR",
                            "Missing dependency",
                            str(file_path),
                            f"Referenced ontology not found: {dep}",
                        )
                    )

    def validate_import_consistency(self, states: Dict[Path, OntologyState]):
        """Validate import statements are consistent."""
        for file_path, state in states.items():
            for imp in state.imports:
                if imp.startswith("./"):
                    imp_path = self.workspace_root / f"{imp[2:]}.ttl"
                    if not imp_path.exists():
                        self.issues.append(
                            ValidationIssue(
                                "ERROR",
                                "Missing import",
                                str(file_path),
                                f"Imported ontology not found: {imp}",
                            )
                        )

    def validate_version_consistency(self, states: Dict[Path, OntologyState]):
        """Validate version numbers are consistent with git history."""
        for file_path, state in states.items():
            try:
                # Get previous version from git history
                result = subprocess.run(
                    ["git", "log", "-1", "--skip=1", "--format=%H", "--", file_path],
                    capture_output=True,
                    text=True,
                    check=True,
                )
                prev_commit = result.stdout.strip()
                if prev_commit:
                    # Get previous file content
                    result = subprocess.run(
                        ["git", "show", f"{prev_commit}:{file_path}"],
                        capture_output=True,
                        text=True,
                        check=True,
                    )
                    prev_content = result.stdout
                    prev_graph = Graph()
                    prev_graph.parse(data=prev_content, format="turtle")

                    # Get previous version
                    prev_version = None
                    for s, _, _ in prev_graph.triples((None, RDF.type, OWL.Ontology)):
                        prev_version = self.extract_version(prev_graph, s)
                        break

                    if prev_version and prev_version >= state.version:
                        self.issues.append(
                            ValidationIssue(
                                "WARNING",
                                "Version not incremented",
                                str(file_path),
                                f"Current version {state.version} not greater than previous {prev_version}",
                            )
                        )
            except subprocess.CalledProcessError:
                # File might be new or not in git yet
                pass

    def validate_required_metadata(self, states: Dict[Path, OntologyState]):
        """Validate presence of required metadata."""
        required_predicates = [
            (RDFS.label, "Label"),
            (RDFS.comment, "Comment"),
            (OWL.versionInfo, "Version info"),
        ]

        for file_path, _ in states.items():
            graph = Graph()
            graph.parse(file_path, format="turtle")

            for s, _, _ in graph.triples((None, RDF.type, OWL.Ontology)):
                for predicate, name in required_predicates:
                    if not any(graph.triples((s, predicate, None))):
                        self.issues.append(
                            ValidationIssue(
                                "WARNING",
                                "Missing metadata",
                                str(file_path),
                                f"Ontology is missing {name}",
                            )
                        )

    def run_validation(self, files: Optional[List[Path]] = None) -> bool:
        """Run all validation checks."""
        self.logger.info("Starting ontology validation")
        self.issues.clear()

        # Get files to validate
        if files is None:
            files = list(self.workspace_root.glob("**/*.ttl"))

        # Get state for each ontology
        states = {}
        for file_path in files:
            state = self.get_ontology_state(file_path)
            if state:
                states[file_path] = state

        # Run validations
        self.validate_cross_references(states)
        self.validate_import_consistency(states)
        self.validate_version_consistency(states)
        self.validate_required_metadata(states)

        # Report issues
        has_errors = False
        for issue in self.issues:
            if issue.severity == "ERROR":
                has_errors = True
                self.logger.error(
                    f"{issue.severity}: {issue.message} in {issue.file}"
                    + (f"\n  {issue.details}" if issue.details else "")
                )
            else:
                self.logger.warning(
                    f"{issue.severity}: {issue.message} in {issue.file}"
                    + (f"\n  {issue.details}" if issue.details else "")
                )

        return not has_errors


def main():
    """Main entry point"""
    workspace_root = Path(__file__).parent.parent
    validator = OntologyValidator(workspace_root)
    success = validator.run_validation()

    if success:
        print("\n✅ Ontology validation successful!")
        exit(0)
    else:
        print("\n❌ Ontology validation failed!")
        print("Please fix the reported issues and run validation again.")
        exit(1)


if __name__ == "__main__":
    main()
