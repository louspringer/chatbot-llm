#!/usr/bin/env python3
"""
ClPM (Claude's Package Manager) - A semantic package manager for Python
projects.

This tool manages Python package dependencies using semantic knowledge from
project ontologies to ensure compatibility, security, and best practices.
"""

import json
import logging
import subprocess
import sys
import tempfile
from dataclasses import dataclass
from enum import Enum, auto
from pathlib import Path
from typing import Dict, List, Optional, Protocol, Tuple, Union

import click
import jsonschema
import toml
import yaml
from packaging.specifiers import SpecifierSet
from packaging.version import Version
from rdflib import Graph, Literal, Namespace, URIRef
from rdflib.namespace import RDF, RDFS
from rich.console import Console
from rich.logging import RichHandler
from rich.traceback import install

# Setup rich error handling
install(show_locals=True)
console = Console()

# Setup logging
logging.basicConfig(
    level=logging.DEBUG,
    format="%(asctime)s - %(name)s - %(levelname)s - %(message)s",
)
logger = logging.getLogger(__name__)

# Timeouts in seconds
AVAILABILITY_CHECK_TIMEOUT = 5
SCAN_TIMEOUT = 30
PACKAGE_INSTALL_TIMEOUT = 300  # 5 minutes for package installation


class WorkspaceConfig:
    """Centralized configuration for workspace paths and URIs."""

    def __init__(self, workspace_root: Optional[Path] = None):
        """Initialize workspace configuration.

        Args:
            workspace_root: Optional workspace root path. If not provided,
                          defaults to current working directory.
        """
        self.workspace_root = workspace_root or Path.cwd()
        self.ontology_dir = self.workspace_root

        # Initialize namespaces
        self.pkg_ns = Namespace("file://package_management#")
        self.sec_ns = Namespace("file://security#")

        # Initialize file paths
        self.pyproject_path = self.workspace_root / "pyproject.toml"
        self.environment_yml_path = self.workspace_root / "environment.yml"
        self.requirements_txt_path = self.workspace_root / "requirements.txt"
        self.package_management_ttl_path = (
            self.workspace_root / "package_management.ttl"
        )
        self.security_ttl_path = self.workspace_root / "security.ttl"

    def get_package_uri(self, package_name: str) -> URIRef:
        """Get URI for a package."""
        return URIRef(f"{self.pkg_ns}{package_name.replace('-', '_')}")

    def get_vulnerability_uri(self, vuln_id: str) -> URIRef:
        """Get URI for a vulnerability."""
        return URIRef(f"{self.sec_ns}#{vuln_id}")


# Initialize default configuration
config = WorkspaceConfig()
PKG = config.pkg_ns
SEC = config.sec_ns

# Base directory for ontologies
WORKSPACE_ROOT = Path(__file__).resolve().parent  # noqa: E501
ONTOLOGY_DIR = WORKSPACE_ROOT  # noqa: E501


class SecurityProvider(Enum):
    """Available security check providers."""

    SAFETY = auto()
    PIP_AUDIT = auto()


@dataclass
class DependencySpec:
    name: str
    version: Optional[str]
    dep_type: str  # core, dev, optional
    source: str  # conda, pip


@dataclass
class SecurityIssue:
    """Represents a security vulnerability found by a scanner.

    Maps to pkg:SecurityVulnerability in the ontology.
    """

    cve_id: str  # Maps to vulnerability ID (CVE or custom)
    description: str  # Maps to rdfs:comment
    severity: str  # Maps to pkg:hasImpact
    affected_versions: str  # Maps to pkg:affectsVersions
    fixed_version: Optional[str]  # Maps to pkg:fixedInVersion
    source: str  # Which security provider found this
    cvss_score: Optional[float] = None  # Maps to pkg:cvssScore
    mitigation_status: Optional[str] = None  # Maps to pkg:mitigationStatus

    _schema = None

    @classmethod
    def _load_schema(cls):
        """Load the JSON schema for validation."""
        if cls._schema is None:
            schema_path = (
                Path(__file__).parent / "schemas" / "security_vulnerability.json"
            )
            try:
                with open(schema_path) as f:
                    cls._schema = json.load(f)
            except Exception as e:
                logger.error("Failed to load security vulnerability schema: %s", e)
                raise

    @staticmethod
    def from_safety_json(data: dict, package: str) -> "SecurityIssue":
        """Create SecurityIssue from safety scanner output."""
        SecurityIssue._load_schema()

        # Add package name to data for validation
        data_with_package = {**data, "package_name": package}

        # Validate against schema
        try:
            jsonschema.validate(
                {"vulnerabilities": [data_with_package]}, SecurityIssue._schema
            )
        except jsonschema.exceptions.ValidationError as e:
            logger.error("Invalid safety scanner output: %s", e)
            raise

        return SecurityIssue(
            cve_id=data.get("CVE") or data.get("vulnerability_id", "Unknown"),
            description=data.get("advisory", "No description available"),
            severity=data.get("severity", "Unknown"),
            affected_versions=", ".join(data.get("vulnerable_spec", [])),
            fixed_version=data.get("fixed_versions", [None])[0],
            source="safety",
            cvss_score=data.get("cvss_score"),
            mitigation_status=data.get("mitigation"),
        )

    @staticmethod
    def from_pip_audit_json(data: dict, package: str) -> "SecurityIssue":
        """Create SecurityIssue from pip-audit scanner output."""
        SecurityIssue._load_schema()

        # Add package name to data for validation
        data_with_package = {**data, "package_name": package}

        # Create schema-compliant structure
        schema_data = {
            "dependencies": [{"name": package, "vulnerabilities": [data_with_package]}]
        }

        # Validate against schema
        try:
            jsonschema.validate(schema_data, SecurityIssue._schema)
        except jsonschema.exceptions.ValidationError as e:
            logger.error("Invalid pip-audit scanner output: %s", e)
            raise

        return SecurityIssue(
            cve_id=data.get("id", "Unknown"),
            description=data.get("description", "No description available"),
            severity=data.get("severity", "Unknown"),
            affected_versions=", ".join(data.get("affected_versions", [])),
            fixed_version=data.get("fixed_version"),
            source="pip-audit",
            cvss_score=data.get("cvss_score"),
        )

    def to_ontology_triples(self, graph: Graph, package: str) -> None:
        """Add this security issue to the ontology graph.

        If the vulnerability already exists, only update if we have new info.
        """
        # Create vulnerability URI without extra #
        vuln_uri = URIRef(f"{SEC}{self.cve_id}")

        # Check if vulnerability already exists
        existing_data = {}
        for _, pred, obj in graph.triples((vuln_uri, None, None)):
            existing_data[pred] = obj

        # Always ensure basic type and package info
        graph.add((vuln_uri, RDF.type, SEC.Vulnerability))
        graph.add((vuln_uri, SEC.affectsPackage, Literal(package)))

        # Update severity if not set or if new severity is more critical
        severity_order = {
            "Critical": 4,
            "High": 3,
            "Medium": 2,
            "Low": 1,
            "Unknown": 0,
        }
        existing_severity = str(existing_data.get(SEC.severity, "Unknown"))
        if severity_order.get(self.severity, 0) > severity_order.get(
            existing_severity, 0
        ):
            graph.remove((vuln_uri, SEC.severity, None))
            graph.add((vuln_uri, SEC.severity, Literal(self.severity)))

        # Update source if we have a new one
        if SEC.source not in existing_data:
            graph.add((vuln_uri, SEC.source, Literal(self.source)))
        elif self.source not in str(existing_data[SEC.source]):
            # Append new source
            sources = f"{existing_data[SEC.source]}, {self.source}"
            graph.remove((vuln_uri, SEC.source, None))
            graph.add((vuln_uri, SEC.source, Literal(sources)))

        # Update fixed version if we have one and it's different
        if self.fixed_version and (
            SEC.fixedVersion not in existing_data
            or str(existing_data[SEC.fixedVersion]) != self.fixed_version
        ):
            graph.remove((vuln_uri, SEC.fixedVersion, None))
            graph.add((vuln_uri, SEC.fixedVersion, Literal(self.fixed_version)))

        # Update CVSS score if higher than existing
        existing_cvss = float(existing_data.get(SEC.cvssScore, 0.0))
        if self.cvss_score is not None and self.cvss_score > existing_cvss:
            graph.remove((vuln_uri, SEC.cvssScore, None))
            graph.add((vuln_uri, SEC.cvssScore, Literal(self.cvss_score)))

        # Update mitigation status if changed
        if self.mitigation_status and (
            SEC.mitigationStatus not in existing_data
            or str(existing_data[SEC.mitigationStatus]) != self.mitigation_status
        ):
            graph.remove((vuln_uri, SEC.mitigationStatus, None))
            graph.add(
                (
                    vuln_uri,
                    SEC.mitigationStatus,
                    Literal(self.mitigation_status),
                )
            )


class SecurityScanner(Protocol):
    """Protocol for security scanners."""

    @property
    def name(self) -> str:
        """Get scanner name."""
        ...

    def is_available(self) -> bool:
        """Check if scanner is available."""
        ...

    def scan_package(self, package: str, version: str) -> List[SecurityIssue]:
        """Scan package for security issues."""
        ...


class SafetyScanner:
    """Safety DB security scanner."""

    @property
    def name(self) -> str:
        """Get scanner name."""
        return "safety"

    def is_available(self) -> bool:
        try:
            subprocess.run(["safety", "--version"], capture_output=True, check=True)
            return True
        except (subprocess.CalledProcessError, FileNotFoundError):
            return False

    def scan_package(self, package: str, version: str) -> List[SecurityIssue]:
        """Scan a package for security vulnerabilities using safety."""
        try:
            logger.debug(
                "Starting safety scan for package %s version %s",
                package,
                version,
            )
            # Create temporary requirements file
            with tempfile.NamedTemporaryFile(mode="w", suffix=".txt") as req_file:
                req_file.write(f"{package}=={version}\n")
                req_file.flush()

                # Run safety check
                cmd = [
                    "safety",
                    "scan",
                    "--file",
                    req_file.name,
                    "--json",
                    "--no-deps",  # Only check the specified package
                    "--progress-spinner",
                    "off",  # Disable progress spinner for cleaner output
                ]
                result = subprocess.run(
                    cmd,
                    capture_output=True,
                    text=True,
                    check=False,
                    timeout=30,
                )
                logger.debug(
                    "Safety check completed with return code %d",
                    result.returncode,
                )

                # Check for authentication requirement
                if "Please login or register Safety CLI" in result.stdout:
                    logger.warning("Safety scanner requires authentication, skipping")
                    return []

                # Parse JSON output
                try:
                    json_lines = [
                        line
                        for line in result.stdout.splitlines()
                        if line.strip().startswith("{")
                    ]
                    if not json_lines:
                        logger.warning("No JSON data found in safety output")
                        return []

                    data = json.loads(json_lines[0])
                    vulnerabilities = data.get("vulnerabilities", [])
                    issues = []

                    for vuln in vulnerabilities:
                        # Add package name if not present
                        if "package_name" not in vuln:
                            vuln["package_name"] = package
                        try:
                            issue = SecurityIssue.from_safety_json(vuln, package)
                            issues.append(issue)
                            logger.debug(
                                "Found vulnerability %s for %s %s",
                                issue.cve_id,
                                package,
                                version,
                            )
                        except jsonschema.exceptions.ValidationError as e:
                            logger.error("Invalid vulnerability data: %s", e)
                            continue

                    return issues

                except json.JSONDecodeError as e:
                    logger.error("Failed to parse safety JSON: %s", e)
                    logger.debug("Attempted to parse JSON: %s", "".join(json_lines))
                    return []

        except subprocess.TimeoutExpired as e:
            logger.error("Safety check timed out: %s", e)
            return []
        except Exception as e:
            logger.error("Error during safety scan: %s", str(e))
            return []

    def _version_matches_spec(self, version: str, spec: str) -> bool:
        """Check if a version matches a version specifier."""
        try:
            version_obj = Version(version)
            specifier_set = SpecifierSet(spec)
            return version_obj in specifier_set
        except Exception as e:
            logger.error(
                "Failed to check version %s against spec %s: %s",
                version,
                spec,
                e,
            )
            return False

    def _validate_version_constraints(
        self, package: str, version: Optional[str]
    ) -> bool:
        if not version:
            return True

        # TODO: Implement version constraint validation
        return True

    def add_package(
        self,
        package: str,
        version: Optional[str],
        dep_type: str,
        use_conda: bool = True,
    ) -> bool:
        try:
            # Validate version constraints
            if not self._validate_version_constraints(package, version):
                if not click.confirm("\nInstall despite version constraint violation?"):
                    return False

            # Install package
            pkg_spec = f"{package}=={version}" if version else package
            conda_path = "/Users/lou/miniconda3/bin/conda"
            if use_conda:
                cmd = [
                    conda_path,
                    "install",
                    "-y",
                    "-c",
                    "conda-forge",
                    pkg_spec,
                ]
                logger.debug("Installing with conda: %s", " ".join(cmd))
            else:
                cmd = ["pip", "install", pkg_spec]
                logger.debug("Installing with pip: %s", " ".join(cmd))

            try:
                # Run command in the workspace directory
                result = subprocess.run(
                    cmd,
                    check=True,
                    capture_output=True,
                    text=True,
                    cwd=str(ONTOLOGY_DIR),
                )
                logger.debug("Installation output:\n%s", result.stdout)
                return True
            except subprocess.CalledProcessError as e:
                logger.error("Installation failed:\n%s", e.stderr)
                return False

        except Exception as e:
            logger.error("Failed to install package: %s", str(e))
            return False


class PipAuditScanner:
    """pip-audit security scanner."""

    @property
    def name(self) -> str:
        """Get scanner name."""
        return "pip-audit"

    def is_available(self) -> bool:
        try:
            subprocess.run(["pip-audit", "--version"], capture_output=True, check=True)
            return True
        except (subprocess.CalledProcessError, FileNotFoundError):
            return False

    def scan_package(self, package: str, version: str) -> List[SecurityIssue]:
        """Scan a package for security vulnerabilities using pip-audit."""
        try:
            logger.debug("Starting pip-audit scan for %s version %s", package, version)
            # Create temporary requirements file
            with tempfile.NamedTemporaryFile(mode="w", suffix=".txt") as req_file:
                req_file.write(f"{package}=={version}\n")
                req_file.flush()

                # Run pip-audit check
                cmd = [
                    "pip-audit",
                    "--requirement",
                    req_file.name,
                    "--format",
                    "json",
                    "--no-deps",  # Only check the specified package
                    "--progress-spinner",
                    "off",  # Disable progress spinner for cleaner output
                ]
                result = subprocess.run(
                    cmd,
                    capture_output=True,
                    text=True,
                    check=False,
                    timeout=30,
                )
                logger.debug(
                    "Pip-audit completed with return code %d",
                    result.returncode,
                )

                # Parse JSON output
                try:
                    if not result.stdout.strip():
                        logger.debug("No output from pip-audit")
                        return []

                    data = json.loads(result.stdout)
                    issues = []

                    # Handle both possible output formats
                    if isinstance(data, list):
                        # New format: list of vulnerabilities
                        for vuln in data:
                            if vuln.get("name") == package:
                                for finding in vuln.get("vulns", []):
                                    try:
                                        issue = SecurityIssue(
                                            cve_id=finding.get("id", "Unknown"),
                                            description=finding.get(
                                                "description", "No description"
                                            ),
                                            severity=finding.get("severity", "Unknown"),
                                            affected_versions=finding.get(
                                                "affected", ""
                                            ),
                                            fixed_version=finding.get(
                                                "fix_versions", [""]
                                            )[0],
                                            source="pip-audit",
                                            cvss_score=finding.get("cvss_score"),
                                        )
                                        issues.append(issue)
                                        logger.debug(
                                            "Found vulnerability %s for %s %s",
                                            issue.cve_id,
                                            package,
                                            version,
                                        )
                                    except Exception as e:
                                        logger.error(
                                            "Failed to create issue from finding: %s",
                                            e,
                                        )
                                        continue
                    elif "dependencies" in data:
                        # Old format: dependencies with vulnerabilities
                        for dep in data["dependencies"]:
                            if dep["name"] == package:
                                for vuln in dep.get("vulnerabilities", []):
                                    try:
                                        issue = SecurityIssue.from_pip_audit_json(
                                            vuln, package
                                        )
                                        issues.append(issue)
                                        logger.debug(
                                            "Found vulnerability %s for %s %s",
                                            issue.cve_id,
                                            package,
                                            version,
                                        )
                                    except jsonschema.exceptions.ValidationError as e:
                                        logger.error(
                                            "Invalid vulnerability data: %s", e
                                        )
                                        continue

                    return issues

                except json.JSONDecodeError as e:
                    logger.error("Failed to parse pip-audit output: %s", e)
                    logger.debug("Raw output: %s", result.stdout)
                    return []

        except subprocess.TimeoutExpired as e:
            logger.error("Pip-audit check timed out: %s", e)
            return []
        except Exception as e:
            logger.error("Error during pip-audit scan: %s", str(e))
            return []


class SecurityChecker:
    """Handles security checks using multiple scanners."""

    def __init__(self, graph: Graph, workspace_root: Optional[Path] = None):
        self.graph = graph
        self.config = WorkspaceConfig(workspace_root)
        self.scanners: List[SecurityScanner] = []

        # Register available scanners
        for scanner in [SafetyScanner(), PipAuditScanner()]:
            if scanner.is_available():
                self.scanners.append(scanner)
                logger.info("Registered %s scanner", scanner.name)
            else:
                logger.warning("%s not available, skipping", scanner.name)

    def _add_to_ontology(self, package: str, issue: SecurityIssue) -> None:
        """Add security issue to the ontology."""
        issue.to_ontology_triples(self.graph, package)

    def check_package(
        self, package: str, version: str
    ) -> Tuple[bool, List[SecurityIssue]]:
        """Check package security using all available scanners."""
        logger.debug("Starting security check for %s version %s", package, version)
        all_issues = []
        is_safe = True
        safety_auth_required = False

        for scanner in self.scanners:
            try:
                logger.debug("Using scanner: %s", scanner.name)
                issues = scanner.scan_package(package, version)

                if isinstance(scanner, SafetyScanner) and not issues:
                    # Check if safety scanner requires auth
                    safety_auth_required = True
                    logger.warning("Safety scanner requires authentication")
                    continue

                if issues:
                    is_safe = False
                    logger.debug(
                        "Found %d issues with %s scanner",
                        len(issues),
                        scanner.name,
                    )

                    # Add each issue to the ontology and our list
                    for issue in issues:
                        self._add_to_ontology(package, issue)
                        all_issues.append(issue)
                else:
                    logger.debug("No issues found with %s scanner", scanner.name)
            except Exception as e:
                logger.error("Error scanning with %s: %s", scanner.name, str(e))

        # If safety scanner requires auth and no issues found yet, try pip-audit
        if safety_auth_required and not all_issues:
            logger.info("Safety scanner requires auth, trying pip-audit")
            pip_audit = PipAuditScanner()
            if pip_audit.is_available():
                try:
                    issues = pip_audit.scan_package(package, version)
                    if issues:
                        is_safe = False
                        for issue in issues:
                            self._add_to_ontology(package, issue)
                            all_issues.append(issue)
                except Exception as e:
                    logger.error("Error with pip-audit fallback: %s", str(e))

        # Deduplicate issues by CVE ID
        seen = set()
        unique_issues = []
        for issue in all_issues:
            if issue.cve_id not in seen:
                seen.add(issue.cve_id)
                unique_issues.append(issue)

        logger.debug(
            "Security check complete. Safe: %s, Issues: %d",
            is_safe,
            len(unique_issues),
        )
        return is_safe, unique_issues


class PackageManager:
    """Core package management functionality."""

    def __init__(self, workspace_root: Optional[Path] = None):
        """Initialize package manager.

        Args:
            workspace_root: Optional workspace root path. If not provided,
                          uses current working directory.
        """
        self.config = WorkspaceConfig(workspace_root)
        self.graph = Graph()

        # Load ontologies
        if not self.config.package_management_ttl_path.exists():
            logger.error(
                f"Ontology file not found: {self.config.package_management_ttl_path}"
            )
            sys.exit(1)

        logger.debug(f"Loading ontology from {self.config.package_management_ttl_path}")
        self.graph.parse(self.config.package_management_ttl_path, format="turtle")

        try:
            self.graph.parse(self.config.security_ttl_path, format="turtle")
        except Exception as e:
            logger.warning(f"Could not load security ontology: {e}")

        self.security = SecurityChecker(self.graph, workspace_root)

    def _check_security(
        self, package: str, version: str
    ) -> Tuple[bool, List[SecurityIssue]]:
        """Check package for known security issues."""
        try:
            # Run security check
            return self.security.check_package(package, version)
        except Exception as e:
            logger.error(f"Security check failed: {e}")
            return False, []

    def _validate_version_constraints(
        self, package: str, version: Optional[str]
    ) -> bool:
        """Validate version against known constraints."""
        if version is None:
            return True

        try:
            pkg_uri = URIRef(f"{self.config.pkg_ns}{package.replace('-', '_')}")
            constraints = (
                list(self.graph.objects(pkg_uri, self.config.pkg_ns.versionConstraint))
                or []
            )

            if not constraints:
                return True

            ver = Version(version)
            for constraint in constraints:
                if not isinstance(constraint, (str, Literal)):
                    continue
                spec = SpecifierSet(str(constraint))
                if ver not in spec:
                    logger.error(f"Version {version} violates constraint {constraint}")
                    return False

            return True
        except Exception as e:
            logger.error(f"Version validation failed: {e}")
            return False

    def _get_all_dependencies(self) -> List[DependencySpec]:
        """Get all current dependencies from ontology."""
        logger.debug("Getting all dependencies from ontology")
        deps = []
        seen_packages = set()
        for pkg in self.graph.subjects(RDF.type, self.config.pkg_ns.Package):
            logger.debug(f"Found package: {pkg}")
            name = str(pkg).split("#")[-1].replace("_", "-")
            if name in seen_packages:
                continue
            seen_packages.add(name)

            dep_type = str(
                self.graph.value(pkg, self.config.pkg_ns.dependencyType)
            ).split("#")[-1]
            version = str(self.graph.value(pkg, self.config.pkg_ns.hasVersion))
            source = str(self.graph.value(pkg, self.config.pkg_ns.hasSource)).split(
                "#"
            )[-1]
            source = "conda" if source == "CondaSource" else "pip"

            logger.debug(
                f"Package details: type={dep_type}, version={version}, source={source}"
            )
            deps.append(
                DependencySpec(
                    name=name,
                    version=version if version != "None" else None,
                    dep_type=(dep_type.lower() if dep_type != "None" else "core"),
                    source=source,
                )
            )
        logger.debug(f"Found {len(deps)} total dependencies")
        return deps

    def _update_pyproject_toml(self, deps: List[DependencySpec]) -> None:
        """Update pyproject.toml with current dependencies."""
        try:
            logger.debug("Starting pyproject.toml update")
            pyproject_path = self.config.pyproject_path
            logger.debug("Using pyproject.toml at: %s", pyproject_path)

            # Create default pyproject.toml if it doesn't exist
            if not pyproject_path.exists():
                logger.info("Creating new pyproject.toml")
                with open(pyproject_path, "w") as f:
                    f.write(
                        """[project]
name = "chatbot-llm"
version = "0.1.0"
dependencies = []

[project.optional-dependencies]
dev = []
"""
                    )

            # Read current pyproject.toml
            logger.debug("Reading current pyproject.toml")
            with open(pyproject_path, "r") as f:
                pyproject = toml.load(f)

            # Initialize dependencies if not present
            if "project" not in pyproject:
                logger.debug("Adding project section")
                pyproject["project"] = {}
            if "dependencies" not in pyproject["project"]:
                logger.debug("Initializing dependencies list")
                pyproject["project"]["dependencies"] = []
            if "optional-dependencies" not in pyproject["project"]:
                logger.debug("Initializing optional dependencies")
                pyproject["project"]["optional-dependencies"] = {}
            if "dev" not in pyproject["project"]["optional-dependencies"]:
                pyproject["project"]["optional-dependencies"]["dev"] = []

            # Get current dependencies
            core_deps = pyproject["project"]["dependencies"]
            dev_deps = pyproject["project"]["optional-dependencies"]["dev"]
            logger.debug("Current core dependencies: %s", core_deps)
            logger.debug("Current dev dependencies: %s", dev_deps)

            # Update dependencies
            for dep in deps:
                spec = f"{dep.name}=={dep.version}" if dep.version else dep.name
                logger.debug(
                    "Processing dependency: %s (type: %s)",
                    spec,
                    dep.dep_type.lower(),
                )
                if dep.dep_type.lower() == "coredependency":
                    if spec not in core_deps:
                        logger.debug("Adding %s to core dependencies", spec)
                        core_deps.append(spec)
                elif dep.dep_type.lower() == "developmentdependency":
                    if spec not in dev_deps:
                        logger.debug("Adding %s to dev dependencies", spec)
                        dev_deps.append(spec)

            # Update pyproject.toml
            logger.debug("Updating pyproject.toml with new dependencies")
            pyproject["project"]["dependencies"] = core_deps
            pyproject["project"]["optional-dependencies"]["dev"] = dev_deps

            # Write updated pyproject.toml
            logger.debug("Writing updated pyproject.toml")
            with open(pyproject_path, "w") as f:
                toml.dump(pyproject, f)

            logger.info("Updated pyproject.toml")

        except Exception as e:
            logger.error("Failed to update pyproject.toml: %s", e)
            raise

    def _update_environment_yml(self, deps: List[DependencySpec]) -> None:
        """Update environment.yml with current dependencies."""
        try:
            env_path = Path.cwd() / "environment.yml"
            # Create default environment.yml if it doesn't exist
            if not env_path.exists():
                logger.info("Creating new environment.yml")
                with open(env_path, "w") as f:
                    f.write(
                        """name: chatbot-llm
channels:
  - conda-forge
  - defaults
dependencies:
  - python>=3.8
  - pip
"""
                    )

            # Read current environment.yml
            with open(env_path) as f:
                env_config = yaml.safe_load(f)

            # Initialize dependencies if not present
            if "dependencies" not in env_config:
                env_config["dependencies"] = []

            # Separate conda and pip dependencies
            conda_deps = [d for d in env_config["dependencies"] if isinstance(d, str)]
            pip_deps = []
            pip_dict = next(
                (
                    d
                    for d in env_config["dependencies"]
                    if isinstance(d, dict) and "pip" in d
                ),
                None,
            )
            if pip_dict:
                pip_deps = pip_dict["pip"]

            # Add new dependencies
            for dep in deps:
                spec = f"{dep.name}=={dep.version}" if dep.version else dep.name
                if dep.source == "conda":
                    if spec not in conda_deps:
                        conda_deps.append(spec)
                else:
                    if spec not in pip_deps:
                        pip_deps.append(spec)

            # Update environment.yml
            env_config["dependencies"] = conda_deps
            if pip_deps:
                env_config["dependencies"].append({"pip": pip_deps})

            # Write updated environment.yml
            with open(env_path, "w") as f:
                yaml.safe_dump(env_config, f, default_flow_style=False)

            logger.info("Updated environment.yml")

        except Exception as e:
            logger.error(f"Failed to update environment.yml: {e}")

    def _update_requirements_txt(self, deps: List[DependencySpec]) -> None:
        """Update requirements.txt with current dependencies."""
        try:
            requirements_path = self.config.requirements_txt_path
            # Combine all pip dependencies
            pip_deps = []
            for dep in deps:
                if dep.source == "pip":
                    spec = f"{dep.name}=={dep.version}" if dep.version else dep.name
                    pip_deps.append(spec)

            # Write updated requirements.txt
            if pip_deps:
                with open(requirements_path, "w") as f:
                    f.write("\n".join(pip_deps) + "\n")
                logger.info("Updated requirements.txt")

        except Exception as e:
            logger.error("Failed to update requirements.txt: %s", e)
            raise

    def _sync_dependency_files(self) -> None:
        """Sync all dependency files with the ontology."""
        deps = self._get_all_dependencies()
        self._update_pyproject_toml(deps)
        self._update_environment_yml(deps)
        self._update_requirements_txt(deps)

    def add_package(
        self,
        package: str,
        version: Optional[str],
        dep_type: str,
        use_conda: bool = True,
    ) -> bool:
        """Add a new package dependency."""
        try:
            logger.debug(
                "Starting package addition - Package: %s, Version: %s, "
                "Type: %s, Conda: %s",
                package,
                version,
                dep_type,
                use_conda,
            )

            # Create package URI and add to ontology
            logger.debug("Adding package to ontology")
            package_uri = self.config.get_package_uri(package)
            dep_types = {
                "core": self.config.pkg_ns.CoreDependency,
                "dev": self.config.pkg_ns.DevelopmentDependency,
                "optional": self.config.pkg_ns.OptionalDependency,
            }

            # Add to ontology
            self.graph.add((package_uri, RDF.type, self.config.pkg_ns.Package))
            self.graph.add(
                (
                    package_uri,
                    self.config.pkg_ns.dependencyType,
                    dep_types[dep_type],
                )
            )
            self.graph.add(
                (
                    package_uri,
                    self.config.pkg_ns.hasVersion,
                    Literal(version if version else "*"),
                )
            )
            self.graph.add(
                (
                    package_uri,
                    self.config.pkg_ns.hasSource,
                    (
                        self.config.pkg_ns.CondaSource
                        if use_conda
                        else self.config.pkg_ns.PipSource
                    ),
                )
            )

            # Serialize ontology changes
            logger.debug("Serializing ontology changes")
            self.graph.serialize(
                self.config.package_management_ttl_path, format="turtle"
            )

            # Get all current dependencies
            deps = self._get_all_dependencies()

            # Update dependency files
            logger.debug("Updating dependency files")
            self._update_pyproject_toml(deps)
            self._update_environment_yml(deps)
            self._update_requirements_txt(deps)

            # Install package
            pkg_spec = f"{package}=={version}" if version else package
            installation_success = False

            if use_conda:
                cmd = ["conda", "install", "-y", "-c", "conda-forge", pkg_spec]
                logger.debug("Installing with conda: %s", " ".join(cmd))
                try:
                    result = subprocess.run(
                        cmd,
                        check=True,
                        capture_output=True,
                        text=True,
                        cwd=str(self.config.workspace_root),
                        timeout=PACKAGE_INSTALL_TIMEOUT,
                    )
                    logger.debug("Conda installation output:\n%s", result.stdout)
                    installation_success = True
                except subprocess.CalledProcessError as e:
                    msg = "Conda installation failed, falling back to pip:\n%s"
                    logger.warning(msg, e.stderr)
                except subprocess.TimeoutExpired as e:
                    msg = "Conda installation timed out after %d seconds"
                    logger.error(msg, e.timeout)
                    return False

            # If conda failed or wasn't requested, try pip
            if not installation_success:
                cmd = ["pip", "install", pkg_spec]
                logger.debug("Installing with pip: %s", " ".join(cmd))
                try:
                    result = subprocess.run(
                        cmd,
                        check=True,
                        capture_output=True,
                        text=True,
                        cwd=str(self.config.workspace_root),
                        timeout=PACKAGE_INSTALL_TIMEOUT,
                    )
                    logger.debug("Pip installation output:\n%s", result.stdout)
                    # Update source to PipSource since we used pip
                    self.graph.remove((package_uri, self.config.pkg_ns.hasSource, None))
                    self.graph.add(
                        (
                            package_uri,
                            self.config.pkg_ns.hasSource,
                            self.config.pkg_ns.PipSource,
                        )
                    )
                    self.graph.serialize(
                        self.config.package_management_ttl_path,
                        format="turtle",
                    )
                    installation_success = True
                except subprocess.CalledProcessError as e:
                    msg = "Pip installation failed:\n%s"
                    logger.error(msg, e.stderr)
                except subprocess.TimeoutExpired as e:
                    msg = "Pip installation timed out after %d seconds"
                    logger.error(msg, e.timeout)

            return installation_success

        except Exception as e:
            logger.error("Unexpected error during package addition: %s", str(e))
            import traceback

            logger.debug("Full traceback:\n%s", traceback.format_exc())
            return False


# Initialize package manager
pkg_mgr = PackageManager()


@click.group()
@click.option("--debug", is_flag=True, help="Enable debug logging")
def cli(debug: bool = False):
    """ClPM - Claude's Package Manager

    A semantic package manager for Python projects that enforces best practices
    through ontology-driven dependency management.
    """
    if debug:
        logger.setLevel(logging.DEBUG)
        logger.debug("Debug logging enabled")


@cli.command()
@click.argument("package")
@click.option("--version", help="Package version constraint")
@click.option(
    "--type",
    type=click.Choice(["core", "dev", "optional"]),
    default="core",
    help="Dependency type",
)
@click.option("--no-conda", is_flag=True, help="Use pip instead of conda")
def add(package: str, version: Optional[str], type: str, no_conda: bool):
    """Add a new package to the project."""
    click.echo(f"Adding package: {package}")
    if pkg_mgr.add_package(package, version, type, not no_conda):
        click.echo("Package added successfully!")
    else:
        click.echo("Failed to add package", err=True)


@cli.command()
@click.argument("package")
@click.option("--version", help="Version to update to")
def update(package: str, version: Optional[str]):
    """Update an existing package."""
    click.echo(f"Updating package: {package}")
    # TODO: Implement package update logic


@cli.command()
@click.argument("package")
def remove(package: str):
    """Remove a package from the project."""
    click.echo(f"Removing package: {package}")
    # TODO: Implement package removal logic


@cli.command()
def check():
    """Check project dependencies for issues."""
    click.echo("Checking dependencies...")
    # TODO: Implement dependency checking logic


@cli.command()
@click.option("--dev", is_flag=True, help="Include development dependencies")
def list(dev: bool):
    """List project dependencies."""
    click.echo("Listing dependencies...")
    # TODO: Implement dependency listing logic


@cli.command()
def sync():
    """Sync dependencies across configuration files."""
    click.echo("Syncing dependencies...")
    # TODO: Implement dependency sync logic


if __name__ == "__main__":
    cli()
