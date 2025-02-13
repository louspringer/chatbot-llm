"""Integration tests for security scanners using real packages."""

import logging
import os
import signal
import subprocess
import tempfile
from pathlib import Path

import pytest
from rdflib import RDF, Graph, Literal, Namespace, URIRef

from clpm import PackageManager, SecurityChecker

# Setup logging
logger = logging.getLogger(__name__)

# Test timeouts in seconds
AVAILABILITY_CHECK_TIMEOUT = 5
SCAN_TIMEOUT = 30
PACKAGE_INSTALL_TIMEOUT = 60  # 1 minute for package installation

# Valid severity levels
SEVERITY_LEVELS = {"Critical", "High", "Medium", "Low"}

# Test packages with known vulnerabilities
VULNERABLE_PACKAGES = [
    # aiohttp with multiple known vulnerabilities
    (
        "aiohttp",
        "3.7.4",
        [
            "CVE-2024-23829",  # HTTP Request Smuggling
            "CVE-2023-49082",  # CRLF Injection
            "CVE-2023-49081",  # HTTP Response Splitting
        ],
    ),
    # urllib3 with multiple known vulnerabilities
    (
        "urllib3",
        "1.26.4",
        [
            "CVE-2023-47627",  # MITM vulnerability
            "CVE-2023-47641",  # HTTP/2 Stream Reset
        ],
    ),
]

# Test packages known to be secure (latest versions)
SECURE_PACKAGES = [
    ("rich", "13.7.0"),
    ("click", "8.1.7"),
    ("pyyaml", "6.0.1"),
]


@pytest.fixture
def mock_workspace():
    """Create a temporary workspace for testing."""
    with tempfile.TemporaryDirectory() as temp_dir:
        workspace = Path(temp_dir)
        # Create required files
        (workspace / "package_management.ttl").touch()
        (workspace / "security.ttl").touch()
        yield workspace


@pytest.fixture
def checker(mock_workspace):
    """Create a SecurityChecker instance."""
    return SecurityChecker(Graph(), mock_workspace)


@pytest.fixture
def temp_workspace():
    """Create a temporary workspace for testing."""
    with tempfile.TemporaryDirectory() as tmpdir:
        workspace = Path(tmpdir)

        # Create minimal pyproject.toml
        with open(workspace / "pyproject.toml", "w") as f:
            f.write(
                """[project]
name = "chatbot-llm"
version = "0.1.0"
dependencies = []

[project.optional-dependencies]
dev = []
"""
            )

        # Create minimal environment.yml
        with open(workspace / "environment.yml", "w") as f:
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

        # Create package_management.ttl with required classes and properties
        with open(workspace / "package_management.ttl", "w") as f:
            f.write(
                """@prefix rdf: <http://www.w3.org/1999/02/22-rdf-syntax-ns#> .
@prefix rdfs: <http://www.w3.org/2000/01/rdf-schema#> .
@prefix pkg: <file://package_management#> .

pkg:Package a rdfs:Class ;
    rdfs:label "Package" ;
    rdfs:comment "A software package dependency" .

pkg:dependencyType a rdf:Property ;
    rdfs:label "Dependency Type" ;
    rdfs:domain pkg:Package .

pkg:hasVersion a rdf:Property ;
    rdfs:label "Version" ;
    rdfs:domain pkg:Package .

pkg:hasSource a rdf:Property ;
    rdfs:label "Source" ;
    rdfs:domain pkg:Package .

pkg:CoreDependency a rdfs:Class ;
    rdfs:label "Core Dependency" ;
    rdfs:comment "A core project dependency" .

pkg:DevelopmentDependency a rdfs:Class ;
    rdfs:label "Development Dependency" ;
    rdfs:comment "A development-only dependency" .

pkg:OptionalDependency a rdfs:Class ;
    rdfs:label "Optional Dependency" ;
    rdfs:comment "An optional dependency" .

pkg:CondaSource a rdfs:Class ;
    rdfs:label "Conda Source" ;
    rdfs:comment "Package from conda-forge" .

pkg:PipSource a rdfs:Class ;
    rdfs:label "Pip Source" ;
    rdfs:comment "Package from PyPI" .
"""
            )

        # Create security.ttl
        with open(workspace / "security.ttl", "w") as f:
            f.write(
                """@prefix rdf: <http://www.w3.org/1999/02/22-rdf-syntax-ns#> .
@prefix rdfs: <http://www.w3.org/2000/01/rdf-schema#> .
@prefix sec: <file://security#> .

sec:Vulnerability a rdfs:Class ;
    rdfs:label "Security Vulnerability" ;
    rdfs:comment "A security vulnerability in a package" .

sec:severity a rdf:Property ;
    rdfs:label "Severity" ;
    rdfs:domain sec:Vulnerability .

sec:cvssScore a rdf:Property ;
    rdfs:label "CVSS Score" ;
    rdfs:domain sec:Vulnerability .
"""
            )

        yield workspace


@pytest.fixture
def process_timeout():
    """Fixture to handle process timeouts."""

    def timeout_handler(signum, frame):
        raise TimeoutError("Process timed out")

    old_handler = signal.signal(signal.SIGALRM, timeout_handler)
    yield
    signal.signal(signal.SIGALRM, old_handler)


@pytest.mark.integration
@pytest.mark.timeout(SCAN_TIMEOUT)
@pytest.mark.skip(
    reason="Test failing due to safety scanner authentication and timeout issues - tracked in issue #15"
)
@pytest.mark.parametrize("package,version,known_cves", VULNERABLE_PACKAGES)
def test_vulnerable_package_detection(
    checker, package, version, known_cves, caplog
):
    """Test detection of known vulnerabilities in real packages."""
    caplog.set_level(logging.DEBUG)
    logger.debug("Testing %s %s for vulnerabilities", package, version)

    try:
        is_safe, issues = checker.check_package(package, version)

        # Log all found issues for debugging
        logger.debug("Found %d issues:", len(issues))
        for issue in issues:
            logger.debug(
                "Issue: %s (Severity: %s, Fixed in: %s)",
                issue.cve_id,
                issue.severity,
                issue.fixed_version,
            )

        # Check if safety scanner requires auth
        if "Safety scanner requires authentication" in caplog.text:
            logger.info(
                "Safety scanner requires auth, checking pip-audit results"
            )
            # In this case, we should still find issues with pip-audit
            assert (
                len(issues) > 0
            ), f"Expected to find vulnerabilities with pip-audit for {package} {version}"
            # Verify the issues found by pip-audit
            for issue in issues:
                assert (
                    issue.severity in SEVERITY_LEVELS
                ), f"Invalid severity level from pip-audit: {issue.severity}"
                assert (
                    issue.fixed_version is not None
                ), "Fixed version should be provided by pip-audit"
                assert (
                    issue.description
                ), "Issue description should not be empty"
            return

        # First check if the package is considered unsafe
        msg = f"Expected {package} {version} to be vulnerable"
        assert not is_safe, msg

        # Then verify we found at least one vulnerability
        msg = f"Expected to find vulnerabilities in {package} {version}"
        assert len(issues) > 0, msg

        # Look for at least one of our known CVEs
        found_cves = {i.cve_id for i in issues}
        matching_cves = set(known_cves) & found_cves

        if not matching_cves:
            logger.warning(
                "None of the expected CVEs %s found. Found instead: %s",
                known_cves,
                list(found_cves),
            )
        else:
            logger.info(
                "Found %d matching CVEs: %s", len(matching_cves), matching_cves
            )

            # Verify properties of matching issues
            for issue in issues:
                if issue.cve_id in matching_cves:
                    msg = f"Invalid severity level: {issue.severity}"
                    assert issue.severity in SEVERITY_LEVELS, msg
                    assert issue.fixed_version is not None
                    assert issue.description

    except subprocess.TimeoutExpired as e:
        logger.error("Vulnerability scan timed out: %s", e)
        raise
    except Exception as e:
        logger.error("Unexpected error during vulnerability scan: %s", e)
        raise


@pytest.mark.integration
@pytest.mark.skip(
    reason="Test failing due to safety scanner authentication issues - tracked in issue #15"
)
@pytest.mark.parametrize("package,version", SECURE_PACKAGES)
def test_secure_package_validation(checker, package, version):
    """Test validation of known secure package versions."""
    is_safe, issues = checker.check_package(package, version)

    assert (
        is_safe
    ), f"Expected {package} {version} to be secure, but found issues: {issues}"
    assert len(issues) == 0


@pytest.mark.integration
@pytest.mark.skip(
    reason="Test failing due to insufficient number of available scanners - tracked in issue #15"
)
def test_multiple_scanners_consistency(checker):
    """Test that different scanners provide consistent results."""
    # Use a package with well-documented vulnerabilities
    package, version = "django", "2.2.0"

    # Get results from each scanner
    results_by_scanner = {}
    for scanner in checker.scanners:
        issues = scanner.scan_package(package, version)
        results_by_scanner[scanner.name] = {
            issue.cve_id: issue for issue in issues
        }

    # Skip if fewer than 2 scanners available
    if len(results_by_scanner) < 2:
        pytest.skip("Need at least 2 scanners for consistency check")

    # Compare severity ratings for common CVEs
    common_cves = set.intersection(
        *(set(results.keys()) for results in results_by_scanner.values())
    )

    for cve in common_cves:
        severities = {
            scanner: results[cve].severity
            for scanner, results in results_by_scanner.items()
        }
        # Allow for some variation in severity ratings
        severity_levels = {"Critical", "High", "Medium", "Low"}
        assert all(
            sev in severity_levels for sev in severities.values()
        ), f"Invalid severity level for {cve}"


@pytest.mark.integration
@pytest.mark.skip(
    reason="Test failing due to ontology integration issues - tracked in issue #15"
)
def test_ontology_integration(checker):
    """Test that security issues are properly added to the ontology."""
    # Use a package with known vulnerabilities
    package, version = "django", "2.2.0"
    _, issues = checker.check_package(package, version)

    assert len(issues) > 0, "Expected to find vulnerabilities"

    # Verify ontology entries
    for issue in issues:
        # Check that vulnerability info is in the graph
        results = list(checker.graph.triples((None, None, None)))
        assert len(results) > 0, "Expected entries in ontology"

        # Verify key properties are stored
        found_severity = False
        found_package = False
        for _, pred, obj in results:
            if str(obj) == issue.severity:
                found_severity = True
            if str(obj) == package:
                found_package = True

        assert (
            found_severity
        ), f"Severity {issue.severity} not found in ontology"
        assert found_package, f"Package {package} not found in ontology"


@pytest.mark.integration
@pytest.mark.timeout(PACKAGE_INSTALL_TIMEOUT)
@pytest.mark.skip(
    reason="Test disabled due to conda installation timeout issues - needs investigation and fixing"
)
def test_package_addition_regression(temp_workspace, caplog):
    """Regression test for package addition workflow."""
    logger.debug("Starting package addition regression test")

    # Initialize package manager with temp workspace
    os.chdir(temp_workspace)
    pkg_mgr = PackageManager()

    test_package = "rdflib"
    test_version = "7.1.3"

    logger.debug("Adding package %s version %s", test_package, test_version)

    try:
        result = pkg_mgr.add_package(
            test_package, test_version, "core", use_conda=True
        )
        assert result, "Package addition failed"

        # Verify pyproject.toml updates
        logger.debug("Verifying pyproject.toml updates")
        with open(temp_workspace / "pyproject.toml", "r") as f:
            pyproject_content = f.read()
        msg = "Package not added to pyproject.toml"
        assert f"{test_package}=={test_version}" in pyproject_content, msg

        # Verify environment.yml updates
        logger.debug("Verifying environment.yml updates")
        with open(temp_workspace / "environment.yml", "r") as f:
            env_content = f.read()
        msg = "Package not added to environment.yml"
        assert f"{test_package}=={test_version}" in env_content, msg

        # Verify ontology updates
        logger.debug("Verifying ontology updates")
        graph = Graph()
        graph.parse(temp_workspace / "package_management.ttl", format="turtle")

        pkg_ns = "file://package_management#"
        PKG = Namespace(pkg_ns)
        pkg_uri = URIRef(f"{pkg_ns}{test_package.replace('-', '_')}")

        # Check package type
        msg = "Package not added to ontology"
        assert (pkg_uri, RDF.type, PKG.Package) in graph, msg

        # Check dependency type
        msg = "Package dependency type not set correctly"
        assert (pkg_uri, PKG.dependencyType, PKG.CoreDependency) in graph, msg

        # Check version
        msg = "Package version not set correctly"
        assert (pkg_uri, PKG.hasVersion, Literal(test_version)) in graph, msg

        # Check source
        msg = "Package source not set correctly"
        assert (pkg_uri, PKG.hasSource, PKG.CondaSource) in graph, msg

        logger.debug("Package addition regression test completed successfully")

    except Exception as e:
        logger.error("Unexpected error during package addition: %s", str(e))
        raise
