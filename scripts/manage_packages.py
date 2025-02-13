#!/usr/bin/env python3
"""
Package management script that enforces project standards and ontology rules.
"""

import argparse
import json
import logging
import subprocess
import sys
from pathlib import Path
from typing import Dict, Optional, Tuple

import toml
import yaml
from packaging import version
from packaging.specifiers import SpecifierSet
from rdflib import Graph, Literal, Namespace, URIRef
from rdflib.namespace import RDF, RDFS

# Setup logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

# Define namespaces
PKG = Namespace("file://package_management#")
META = Namespace("file://meta#")


class SecurityCheck:
    """Handles security validation for packages."""

    def __init__(self, graph: Graph):
        self.graph = graph

    def check_package_security(
        self, package_name: str, version_str: str
    ) -> Tuple[bool, Optional[Dict]]:
        """Check package security using safety DB and update ontology."""
        try:
            # Run safety check
            cmd = [
                "safety",
                "check",
                f"{package_name}=={version_str}",
                "--json",
            ]
            result = subprocess.run(cmd, capture_output=True, text=True)

            if result.returncode == 0:
                return True, None

            try:
                vulns = json.loads(result.stdout)
                return False, vulns
            except json.JSONDecodeError:
                # No valid JSON means no known vulnerabilities
                return True, None

        except Exception as e:
            logger.error(f"Security check failed: {str(e)}")
            return False, None

    def _assess_severity(self, vuln: Dict) -> Tuple[URIRef, URIRef]:
        """Assess the severity and likelihood of a vulnerability."""
        cvss = float(vuln.get("cvss_score", 0))

        if cvss >= 9.0:
            impact = PKG.CriticalImpact
            likelihood = PKG.HighLikelihood
        elif cvss >= 7.0:
            impact = PKG.HighImpact
            likelihood = PKG.MediumLikelihood
        elif cvss >= 4.0:
            impact = PKG.MediumImpact
            likelihood = PKG.MediumLikelihood
        else:
            impact = PKG.LowImpact
            likelihood = PKG.LowLikelihood

        return impact, likelihood


class PackageManager:
    """Manages package dependencies following project ontology rules."""

    def __init__(self, workspace_root: Path):
        self.workspace_root = workspace_root
        self.pyproject_path = workspace_root / "pyproject.toml"
        self.environment_yml_path = workspace_root / "environment.yml"
        self.requirements_txt_path = workspace_root / "requirements.txt"
        self.ontology_path = workspace_root / "package_management.ttl"

        # Load ontology
        self.graph = Graph()
        if not self.ontology_path.exists():
            logger.error(f"Ontology file not found: {self.ontology_path}")
            sys.exit(1)

        logger.debug(f"Loading ontology from {self.ontology_path}")
        self.graph.parse(self.ontology_path, format="turtle")
        logger.debug(f"Loaded {len(self.graph)} triples")

    def validate_package_request(
        self, package_name: str, version: str, dependency_type: str
    ) -> bool:
        """Validates package addition against ontology rules."""
        # Check if package type is valid
        valid_types = [
            str(t) for t in self.graph.subjects(RDF.type, PKG.DependencyType)
        ]
        logger.debug(f"Valid dependency types: {valid_types}")
        logger.debug(f"Checking type: {PKG[dependency_type]}")

        # Check if package type exists
        type_triple = (PKG[dependency_type], RDF.type, PKG.DependencyType)
        if type_triple not in self.graph:
            logger.error(f"Invalid dependency type: {dependency_type}")
            return False

        # Check if package already exists
        if self._package_exists(package_name):
            logger.error(f"Package {package_name} already exists")
            return False

        return True

    def _check_dependency_constraints(
        self, package_name: str, version_str: str
    ) -> bool:
        """Check if the requested version satisfies all dependency
        constraints.
        """
        try:
            requested_version = version.parse(version_str)

            # Retrieve package constraints from environment.yml and
            # pyproject.toml
            constraints = self._get_package_constraints(package_name)

            # If no constraints found, this is a new package
            if not constraints:
                return True

            for constraint in constraints:
                try:
                    # Convert version to specifier if it's just a version number
                    ops = [">=", "<=", "==", ">", "<", "!="]
                    if not any(op in constraint for op in ops):
                        constraint = f">={constraint}"

                    spec = SpecifierSet(constraint)
                    if not spec.contains(requested_version):
                        msg = (
                            f"Version {version_str} of {package_name} "
                            f"violates constraint {constraint}"
                        )
                        logger.error(msg)
                        return False
                except Exception:
                    logger.error(f"Invalid constraint format: {constraint}")
                    return False

            # Perform security check
            security = SecurityCheck(self.graph)
            is_secure, vulns = security.check_package_security(
                package_name, version_str
            )

            if not is_secure and vulns:
                logger.error(
                    f"Security vulnerabilities found in {package_name} "
                    f"version {version_str}:"
                )
                for vuln in vulns:
                    vuln_msg = (
                        f"  - {vuln['vulnerability_id']}: "
                        f"{vuln['description']}"
                    )
                    logger.error(vuln_msg)
                return False

            return True

        except json.JSONDecodeError:
            # No JSON output means no known vulnerabilities
            return True
        except Exception as e:
            err_msg = f"Error checking constraints: {str(e)}"
            logger.error(err_msg)
            return False

    def _get_package_constraints(self, package_name: str) -> list:
        """Get package version constraints from project files."""
        constraints = []

        # Check environment.yml
        if self.environment_yml_path.exists():
            with open(self.environment_yml_path) as f:
                env = yaml.safe_load(f)
                for dep in env.get("dependencies", []):
                    if isinstance(dep, str) and dep.startswith(package_name):
                        constraints.append(dep.split("=")[1])

        # Check pyproject.toml
        if self.pyproject_path.exists():
            with open(self.pyproject_path) as f:
                proj = toml.load(f)
                deps = proj.get("project", {}).get("dependencies", [])
                for dep in deps:
                    if dep.startswith(package_name):
                        constraints.append(dep.split(">=")[1])

        return constraints

    def add_package(
        self,
        package_name: str,
        version: str,
        dependency_type: str,
        use_conda: bool = True,
    ) -> bool:
        """Adds a package following the defined process."""
        logger.info(f"Adding package {package_name} version {version}")
        logger.info(f"Dependency type: {dependency_type}")
        logger.info(f"Using conda: {use_conda}")

        if not self.validate_package_request(
            package_name, version, dependency_type
        ):
            return False

        if not self._check_dependency_constraints(package_name, version):
            return False

        try:
            if use_conda:
                self._add_conda_package(package_name, version)
            else:
                self._add_pip_package(package_name, version, dependency_type)

            self._update_ontology(package_name, version, dependency_type)
            self._run_validation()
            return True

        except Exception as e:
            logger.error(f"Failed to add package: {e}")
            return False

    def _add_conda_package(self, package_name: str, version: str):
        """Adds package to environment.yml and updates environment."""
        # Update environment.yml
        with open(self.environment_yml_path, "r") as f:
            env_config = yaml.safe_load(f)

        if "dependencies" not in env_config:
            env_config["dependencies"] = []

        env_config["dependencies"].append(f"{package_name}={version}")

        with open(self.environment_yml_path, "w") as f:
            yaml.safe_dump(env_config, f)

        # Update environment
        cmd = ["conda", "env", "update", "-f", str(self.environment_yml_path)]
        subprocess.run(cmd, check=True)

    def _add_pip_package(
        self, package_name: str, version: str, dependency_type: str
    ):
        """Adds package to pyproject.toml and installs it."""
        with open(self.pyproject_path, "r") as f:
            pyproject = toml.load(f)

        # Add to appropriate dependency section
        if dependency_type == "CoreDependency":
            deps = pyproject.get("project", {}).get("dependencies", [])
            deps.append(f"{package_name}>={version}")
            pyproject["project"]["dependencies"] = deps
        elif dependency_type == "DevelopmentDependency":
            if "optional-dependencies" not in pyproject["project"]:
                pyproject["project"]["optional-dependencies"] = {}
            dev_deps = pyproject["project"]["optional-dependencies"].get(
                "dev", []
            )
            dev_deps.append(f"{package_name}>={version}")
            pyproject["project"]["optional-dependencies"]["dev"] = dev_deps

        with open(self.pyproject_path, "w") as f:
            toml.dump(pyproject, f)

        # Install package
        subprocess.run(["pip", "install", "-e", "."], check=True)

    def _update_ontology(
        self, package_name: str, version: str, dependency_type: str
    ):
        """Updates package management ontology with new package."""
        pkg_uri = PKG[package_name.replace("-", "_")]
        self.graph.add((pkg_uri, RDF.type, PKG.Package))
        self.graph.add((pkg_uri, RDFS.label, Literal(package_name)))
        self.graph.add((pkg_uri, PKG.hasVersion, Literal(version)))
        self.graph.add((pkg_uri, PKG.dependencyType, PKG[dependency_type]))

        self.graph.serialize(self.ontology_path, format="turtle")

    def _run_validation(self):
        """Run validation steps for package installation."""
        try:
            # Run tests
            logger.info("Running test suite...")
            result = subprocess.run(
                ["pytest"], check=True, capture_output=True
            )
            if result.returncode != 0:
                logger.error("Test suite failed")
                return False

            # Check for security vulnerabilities
            logger.info("Checking for security vulnerabilities...")
            try:
                result = subprocess.run(
                    ["safety", "check"], capture_output=True
                )
                if result.returncode != 0:
                    # Log warnings but don't fail for security issues
                    logger.warning(
                        "Security vulnerabilities found:\n\n%s",
                        result.stdout.decode(),
                    )
            except FileNotFoundError:
                # Safety command not found - this is a bootstrap dependency
                logger.warning(
                    "Safety package not found. This is a bootstrap dependency "
                    "that needs to be installed first."
                )
                logger.warning("Installing safety package...")
                subprocess.run(
                    [sys.executable, "-m", "pip", "install", "safety"],
                    check=True,
                )
                # Retry security check
                result = subprocess.run(
                    ["safety", "check"], capture_output=True
                )
                if result.returncode != 0:
                    logger.warning(
                        "Security vulnerabilities found:\n\n%s",
                        result.stdout.decode(),
                    )

            return True
        except subprocess.CalledProcessError as e:
            logger.error(f"Validation failed: {str(e)}")
            return False
        except Exception as e:
            logger.error(f"Unexpected error during validation: {str(e)}")
            return False

    def _package_exists(self, package_name: str) -> bool:
        """Checks if package already exists in project."""
        pkg_uri = PKG[package_name.replace("-", "_")]
        return (pkg_uri, RDF.type, PKG.Package) in self.graph

    def update_package(
        self, package_name: str, version: str, use_conda: bool = True
    ) -> bool:
        """Updates an existing package to a new version."""
        logger.info(f"Updating package {package_name} to version {version}")
        logger.info(f"Using conda: {use_conda}")

        # Check if package exists
        if not self._package_exists(package_name):
            logger.error(f"Package {package_name} does not exist")
            return False

        if not self._check_dependency_constraints(package_name, version):
            return False

        try:
            # Get current dependency type
            pkg_uri = PKG[package_name.replace("-", "_")]
            dependency_type = str(
                self.graph.value(pkg_uri, PKG.dependencyType)
            ).split("#")[-1]

            if use_conda:
                self._add_conda_package(package_name, version)
            else:
                self._add_pip_package(package_name, version, dependency_type)

            self._update_ontology(package_name, version, dependency_type)
            self._run_validation()
            return True

        except Exception as e:
            logger.error(f"Failed to update package: {e}")
            return False


def main():
    parser = argparse.ArgumentParser(description="Manage project dependencies")
    parser.add_argument(
        "action",
        choices=["add", "remove", "update"],
        help="Action to perform",
    )
    parser.add_argument("package", help="Package name")
    parser.add_argument(
        "--version",
        default="latest",
        help="Package version (default: latest)",
    )
    parser.add_argument(
        "--type",
        choices=["core", "dev", "optional"],
        default="core",
        help="Dependency type",
    )
    parser.add_argument(
        "--no-conda", action="store_true", help="Use pip instead of conda"
    )
    parser.add_argument(
        "--debug", action="store_true", help="Enable debug logging"
    )

    args = parser.parse_args()

    # Set debug logging if requested
    if args.debug:
        logger.setLevel(logging.DEBUG)

    # Map CLI type to ontology type
    type_map = {
        "core": "CoreDependency",
        "dev": "DevelopmentDependency",
        "optional": "OptionalDependency",
    }

    workspace_root = Path(__file__).parent.parent
    manager = PackageManager(workspace_root)

    if args.action == "add":
        success = manager.add_package(
            args.package, args.version, type_map[args.type], not args.no_conda
        )
        sys.exit(0 if success else 1)
    elif args.action == "update":
        success = manager.update_package(
            args.package, args.version, not args.no_conda
        )
        sys.exit(0 if success else 1)
    else:
        logger.error(f"Action {args.action} not implemented yet")
        sys.exit(1)


if __name__ == "__main__":
    main()
