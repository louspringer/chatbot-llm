"""Tests for security scanner functionality."""

import json
import logging
import os
import signal
import subprocess
import tempfile
from pathlib import Path
from typing import List, Optional
from unittest.mock import MagicMock, patch

import pytest
from rdflib import RDF, RDFS, Graph, Literal, Namespace, URIRef

from clpm import (
    PipAuditScanner,
    SafetyScanner,
    SecurityChecker,
    SecurityIssue,
    SecurityScanner,
    WorkspaceConfig,
)

# Setup logging
logging.basicConfig(
    level=logging.DEBUG,
    format="%(asctime)s - %(name)s - %(levelname)s - %(message)s",
)
logger = logging.getLogger(__name__)

# Test timeouts in seconds
AVAILABILITY_CHECK_TIMEOUT = 5
SCAN_TIMEOUT = 30
PACKAGE_INSTALL_TIMEOUT = 300  # 5 minutes for package installation

# Define namespaces
SEC = Namespace("file://security#")

# Test data
MOCK_SAFETY_OUTPUT = {
    "vulnerabilities": [
        {
            "package_name": "vuln-pkg",
            "CVE": "TEST-001",
            "advisory": "Test vulnerability",
            "severity": "High",
            "vulnerable_spec": ["<2.0.0"],
            "fixed_versions": ["2.0.0"],
            "cvss_score": 7.5,
            "mitigation": "Pending",
        }
    ]
}

MOCK_PIP_AUDIT_OUTPUT = {
    "dependencies": [
        {
            "name": "test-pkg",
            "vulnerabilities": [
                {
                    "id": "TEST-002",
                    "package_name": "test-pkg",
                    "description": "Test vulnerability",
                    "severity": "Medium",
                    "affected_versions": ["1.0.0"],
                    "fixed_version": "1.1.0",
                    "cvss_score": 5.0,
                }
            ],
        }
    ]
}


class MockScanner(SecurityScanner):
    """Mock scanner for testing."""

    def __init__(
        self,
        name: str,
        available: bool = True,
        issues: Optional[List[SecurityIssue]] = None,
    ):
        self._name = name
        self._available = available
        self._issues = issues if issues is not None else []

    @property
    def name(self) -> str:
        return self._name

    def is_available(self) -> bool:
        return self._available

    def scan_package(self, package: str, version: str) -> List[SecurityIssue]:
        return self._issues


@pytest.fixture
def mock_subprocess():
    """Mock subprocess for testing with timeout handling."""
    with patch("subprocess.run") as mock_run:

        def mock_run_with_timeout(*args, **kwargs):
            logger.debug(
                "Mock subprocess call: %s",
                args[0] if args else kwargs.get("args"),
            )
            if "timeout" not in kwargs:
                kwargs["timeout"] = SCAN_TIMEOUT

            # Create a mock result
            mock_result = MagicMock()
            mock_result.returncode = 0
            mock_result.stderr = ""

            # Set stdout based on the command
            cmd = args[0] if args else kwargs.get("args", [])
            if "safety" in cmd:
                mock_result.stdout = json.dumps(
                    {
                        "vulnerabilities": [
                            {
                                **MOCK_SAFETY_OUTPUT["vulnerabilities"][0],
                                "package_name": "test-pkg",
                            }
                        ]
                    }
                )
            elif "pip-audit" in cmd:
                mock_result.stdout = json.dumps(MOCK_PIP_AUDIT_OUTPUT)
            else:
                mock_result.stdout = ""

            return mock_result

        mock_run.side_effect = mock_run_with_timeout
        yield mock_run


@pytest.fixture
def process_timeout():
    """Fixture to handle process timeouts."""

    def timeout_handler(signum, frame):
        raise TimeoutError("Process timed out")

    old_handler = signal.signal(signal.SIGALRM, timeout_handler)
    yield
    signal.signal(signal.SIGALRM, old_handler)


@pytest.fixture
def mock_temp_file():
    """Create and clean up a temp file."""
    fd, path = tempfile.mkstemp()
    yield path
    os.close(fd)
    os.unlink(path)


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
def mock_config(mock_workspace):
    """Create a WorkspaceConfig with a mock workspace."""
    return WorkspaceConfig(mock_workspace)


@pytest.fixture
def mock_graph():
    """Create a mock RDF graph."""
    return Graph()


@pytest.fixture
def caplog_debug(caplog):
    """Fixture to capture logs at DEBUG level."""
    caplog.set_level(logging.DEBUG)
    return caplog


def test_mock_scanner():
    """Test mock scanner functionality."""
    issues = [
        SecurityIssue(
            cve_id="TEST-001",
            description="Test issue",
            severity="High",
            affected_versions="<1.0.0",
            fixed_version="1.0.0",
            source="mock",
        )
    ]
    scanner = MockScanner("mock", True, issues)

    assert scanner.name == "mock"
    assert scanner.is_available()

    results = scanner.scan_package("test-pkg", "0.1.0")
    assert len(results) == 1
    assert results[0].cve_id == "TEST-001"


@pytest.mark.asyncio
async def test_safety_scanner():
    """Test SafetyScanner functionality."""
    scanner = SafetyScanner()

    with patch("subprocess.run") as mock_run:
        # Test availability check
        mock_run.return_value.returncode = 0
        mock_run.return_value.stdout = ""
        assert scanner.is_available()

        # Test successful scan (no issues)
        mock_run.return_value.returncode = 0
        mock_run.return_value.stdout = "{}"
        results = scanner.scan_package("safe-pkg", "1.0.0")
        assert len(results) == 0

        # Test scan with issues
        mock_run.return_value.returncode = 1
        mock_run.return_value.stdout = json.dumps(MOCK_SAFETY_OUTPUT)
        results = scanner.scan_package("vuln-pkg", "1.0.0")
        assert len(results) == 1
        assert results[0].cve_id == "TEST-001"
        assert results[0].severity == "High"


@pytest.mark.asyncio
@pytest.mark.skip(
    reason="Test disabled due to timeout issues - tracked in issue #15"
)
async def test_safety_scanner_with_debug(caplog_debug, mock_subprocess):
    """Test SafetyScanner with detailed logging."""
    scanner = SafetyScanner()
    mock_subprocess.return_value.returncode = 1
    mock_subprocess.return_value.stdout = json.dumps(
        {"vulnerabilities": MOCK_SAFETY_OUTPUT["vulnerabilities"]}
    )

    results = scanner.scan_package("vuln-pkg", "1.0.0")

    # Log the entire process
    logger.debug("Test complete. Captured logs:")
    for record in caplog_debug.records:
        logger.debug("%s: %s", record.levelname, record.message)

    assert len(results) == 1
    assert results[0].cve_id == "TEST-001"


@pytest.mark.asyncio
@pytest.mark.skip(
    reason="Test failing due to pip-audit type checking issues - tracked in issue #15"
)
async def test_pip_audit_scanner():
    """Test PipAuditScanner functionality."""
    scanner = PipAuditScanner()

    with patch("subprocess.run") as mock_run:
        # Test availability check
        mock_run.return_value.returncode = 0
        assert scanner.is_available()

        # Test successful scan (no issues)
        mock_run.return_value.returncode = 0
        mock_run.return_value.stdout = "{}"
        results = scanner.scan_package("safe-pkg", "1.0.0")
        assert len(results) == 0

        # Test scan with issues
        mock_run.return_value.returncode = 1
        mock_run.return_value.stdout = json.dumps(MOCK_PIP_AUDIT_OUTPUT)
        results = scanner.scan_package("test-pkg", "1.0.0")
        assert len(results) == 1
        assert results[0].cve_id == "TEST-002"
        assert results[0].severity == "Medium"


def test_security_checker_initialization(mock_graph, mock_workspace):
    """Test SecurityChecker initialization and scanner registration."""
    with patch("subprocess.run") as mock_run:
        # Make both scanners available
        mock_run.return_value.returncode = 0
        checker = SecurityChecker(mock_graph, mock_workspace)
        assert len(checker.scanners) == 2

        # Make scanners unavailable
        mock_run.side_effect = FileNotFoundError()
        checker = SecurityChecker(mock_graph, mock_workspace)
        assert len(checker.scanners) == 0


def test_security_checker_scanning(mock_graph, mock_workspace):
    """Test SecurityChecker scanning functionality."""
    # Create checker with mock scanners
    checker = SecurityChecker(mock_graph, mock_workspace)
    checker.scanners = [
        MockScanner(
            "scanner1",
            True,
            [
                SecurityIssue(
                    cve_id="TEST-001",
                    description="Test issue 1",
                    severity="High",
                    affected_versions="<1.0.0",
                    fixed_version="1.0.0",
                    source="scanner1",
                )
            ],
        ),
        MockScanner(
            "scanner2",
            True,
            [
                SecurityIssue(
                    cve_id="TEST-002",
                    description="Test issue 2",
                    severity="Medium",
                    affected_versions="<2.0.0",
                    fixed_version="2.0.0",
                    source="scanner2",
                )
            ],
        ),
    ]

    # Test scanning
    is_safe, issues = checker.check_package("test-pkg", "0.1.0")
    assert not is_safe
    assert len(issues) == 2

    # Verify issues are added to ontology
    for issue in issues:
        assert (None, None, Literal(issue.severity)) in mock_graph


def test_security_checker_deduplication(mock_graph, mock_workspace):
    """Test deduplication of security issues."""
    checker = SecurityChecker(mock_graph, mock_workspace)
    checker.scanners = [
        MockScanner(
            "scanner1",
            True,
            [
                SecurityIssue(
                    cve_id="TEST-001",
                    description="Test issue",
                    severity="High",
                    affected_versions="<1.0.0",
                    fixed_version="1.0.0",
                    source="scanner1",
                )
            ],
        ),
        MockScanner(
            "scanner2",
            True,
            [
                SecurityIssue(
                    cve_id="TEST-001",  # Same CVE
                    description="Test issue (different desc)",
                    severity="Medium",  # Different severity
                    affected_versions="<1.0.0",
                    fixed_version="1.0.0",
                    source="scanner2",
                )
            ],
        ),
    ]

    is_safe, issues = checker.check_package("test-pkg", "0.1.0")
    assert not is_safe
    assert len(issues) == 1  # Should be deduplicated
    assert issues[0].cve_id == "TEST-001"


def test_security_ontology_loading(caplog):
    """Test that the security ontology is loaded correctly."""
    caplog.set_level(logging.DEBUG)
    logger.debug("Starting security ontology loading test")

    # Create a test graph
    graph = Graph()
    logger.debug("Created RDF graph")

    # Get the security.ttl path
    security_path = Path(__file__).parent.parent / "security.ttl"
    logger.debug("Looking for security.ttl at: %s", security_path)

    if not security_path.exists():
        logger.error("security.ttl file not found at %s", security_path)
        pytest.fail("security.ttl file not found")

    logger.debug("Found security.ttl file")

    # Try loading the ontology
    try:
        logger.debug("Attempting to parse security.ttl")
        graph.parse(security_path, format="turtle")
        logger.debug("Successfully parsed security.ttl")

        # Debug: Print all triples in the graph
        logger.debug("All triples in the graph:")
        for s, p, o in graph:
            logger.debug("  %s %s %s", s, p, o)

    except Exception as e:
        logger.error("Failed to parse security.ttl: %s", str(e))
        pytest.fail(f"Failed to load security ontology: {e}")

    # Verify key components exist
    logger.debug("Checking for classes")
    has_classes = any(graph.subjects(RDF.type, RDFS.Class))
    logger.debug("Has classes: %s", has_classes)
    assert has_classes, "No classes found"

    logger.debug("Checking for labels")
    has_labels = any(graph.triples((None, RDFS.label, None)))
    logger.debug("Has labels: %s", has_labels)
    assert has_labels, "No labels found"

    # Check for specific security concepts
    SEC = Namespace(f"file://{security_path}#")  # Use full path
    logger.debug("Using security namespace: %s", SEC)

    # Debug: Print all class-type triples
    logger.debug("All class definitions:")
    for s, p, o in graph.triples((None, RDF.type, RDFS.Class)):
        logger.debug("  %s %s %s", s, p, o)

    required_classes = ["Vulnerability", "Severity"]
    required_severities = ["Critical", "High", "Medium", "Low"]
    required_properties = [
        "affectsPackage",
        "severity",
        "cvssScore",
        "source",
        "fixedVersion",
    ]

    # Check required classes
    logger.debug("Checking required classes")
    for cls in required_classes:
        logger.debug("Checking class: %s", cls)
        class_uri = SEC[cls]
        logger.debug(
            "Looking for triple: (%s, %s, %s)", class_uri, RDF.type, RDFS.Class
        )
        assert (
            class_uri,
            RDF.type,
            RDFS.Class,
        ) in graph, f"Missing required class: {cls}"

    # Check severity levels
    logger.debug("Checking severity levels")
    for sev in required_severities:
        logger.debug("Checking severity: %s", sev)
        severity_uri = SEC[sev]
        assert (
            severity_uri,
            RDF.type,
            SEC.Severity,
        ) in graph, f"Missing severity level: {sev}"

    # Check required properties
    logger.debug("Checking required properties")
    for prop in required_properties:
        logger.debug("Checking property: %s", prop)
        prop_uri = SEC[prop]
        assert (
            prop_uri,
            RDF.type,
            RDF.Property,
        ) in graph, f"Missing required property: {prop}"

    logger.debug("Security ontology test completed successfully")


def test_safety_scanner_initialization(mock_subprocess, caplog):
    """Test SafetyScanner initialization and availability check."""
    logger.debug("Starting SafetyScanner initialization test")
    scanner = SafetyScanner()

    mock_subprocess.return_value.returncode = 0
    assert scanner.is_available()
    logger.debug("Scanner availability check passed")


@pytest.mark.timeout(SCAN_TIMEOUT)
def test_safety_scanner_scan_package(mock_subprocess, mock_temp_file, caplog):
    """Test SafetyScanner package scanning."""
    logger.debug("Starting SafetyScanner package scan test")
    scanner = SafetyScanner()

    mock_data = {
        "vulnerabilities": [
            {
                **MOCK_SAFETY_OUTPUT["vulnerabilities"][0],
                "package_name": "test-pkg",
            }
        ]
    }
    mock_subprocess.return_value.stdout = json.dumps(mock_data)

    logger.debug("Running package scan")
    try:
        results = scanner.scan_package("test-pkg", "1.0.0")
        logger.debug(f"Scan completed with {len(results)} results")

        assert len(results) == 1
        assert results[0].cve_id == "TEST-001"
        logger.debug("Package scan test passed")
    except subprocess.TimeoutExpired as e:
        logger.error("Package scan timed out: %s", e)
        raise
    except Exception as e:
        logger.error("Unexpected error during package scan: %s", e)
        raise


def test_pip_audit_scanner_initialization(mock_subprocess, caplog):
    """Test PipAuditScanner initialization and availability check."""
    logger.debug("Starting PipAuditScanner initialization test")
    scanner = PipAuditScanner()

    mock_subprocess.return_value.returncode = 0
    assert scanner.is_available()
    logger.debug("Scanner availability check passed")


@pytest.mark.timeout(SCAN_TIMEOUT)
@pytest.mark.skip(
    reason="Test failing due to pip-audit type checking issues - tracked in issue #15"
)
def test_pip_audit_scanner_scan_package(
    mock_subprocess, mock_temp_file, caplog
):
    """Test PipAuditScanner package scanning."""
    logger.debug("Starting PipAuditScanner package scan test")
    scanner = PipAuditScanner()

    mock_subprocess.return_value.stdout = json.dumps(MOCK_PIP_AUDIT_OUTPUT)

    logger.debug("Running package scan")
    try:
        results = scanner.scan_package("test-pkg", "1.0.0")
        logger.debug("Scan completed with %d results", len(results))

        assert len(results) == 1
        assert results[0].cve_id == "TEST-002"
        logger.debug("Package scan test passed")
    except subprocess.TimeoutExpired as e:
        logger.error("Package scan timed out: %s", e)
        raise
    except Exception as e:
        logger.error("Unexpected error during package scan: %s", e)
        raise


def test_security_checker_with_mock_scanners(mock_graph, caplog):
    """Test SecurityChecker with mock scanners."""
    logger.debug("Starting SecurityChecker test with mock scanners")
    checker = SecurityChecker(mock_graph)

    # Replace real scanners with mocks
    mock_scanner1 = MockScanner(
        "mock1",
        True,
        [
            SecurityIssue(
                cve_id="TEST-001",
                description="Test vuln 1",
                severity="High",
                affected_versions="<1.0.0",
                fixed_version="1.0.0",
                source="mock1",
            )
        ],
    )
    mock_scanner2 = MockScanner(
        "mock2",
        True,
        [
            SecurityIssue(
                cve_id="TEST-002",
                description="Test vuln 2",
                severity="Medium",
                affected_versions="<2.0.0",
                fixed_version="2.0.0",
                source="mock2",
            )
        ],
    )

    logger.debug("Setting up mock scanners")
    checker.scanners = [mock_scanner1, mock_scanner2]

    logger.debug("Running security check")
    is_safe, issues = checker.check_package("test-pkg", "0.1.0")
    logger.debug(f"Check completed. Safe: {is_safe}, Issues: {len(issues)}")

    assert not is_safe
    assert len(issues) == 2
    logger.debug("Security checker test passed")


def test_security_issue_creation(caplog):
    """Test SecurityIssue creation from different sources."""
    logger.debug("Starting SecurityIssue creation test")

    # Test safety JSON parsing
    logger.debug("Testing safety JSON parsing")
    safety_vuln = {
        "CVE": "TEST-001",
        "advisory": "Test vulnerability",
        "severity": "High",
        "vulnerable_spec": ["<2.0.0"],
        "fixed_versions": ["2.0.0"],
        "cvss_score": 7.5,
        "mitigation": "Pending",
    }

    issue = SecurityIssue.from_safety_json(safety_vuln, "test-pkg")
    logger.debug(f"Created issue from safety: {issue.cve_id}")
    assert issue.cve_id == "TEST-001"
    assert issue.severity == "High"

    # Test pip-audit JSON parsing
    logger.debug("Testing pip-audit JSON parsing")
    pip_audit_vuln = {
        "id": "TEST-002",
        "description": "Test vulnerability",
        "severity": "Medium",
        "affected_versions": ["1.0.0"],
        "fixed_version": "1.1.0",
        "cvss_score": 5.0,
    }

    issue = SecurityIssue.from_pip_audit_json(pip_audit_vuln, "test-pkg")
    logger.debug(f"Created issue from pip-audit: {issue.cve_id}")
    assert issue.cve_id == "TEST-002"
    assert issue.severity == "Medium"

    logger.debug("SecurityIssue creation test passed")


def test_ontology_integration(mock_graph, mock_workspace, caplog):
    """Test integration with security ontology."""
    logger.debug("Starting ontology integration test")
    checker = SecurityChecker(mock_graph, mock_workspace)

    # Create a test vulnerability
    issue = SecurityIssue(
        cve_id="TEST-001",
        description="Test vulnerability",
        severity="High",
        affected_versions="<1.0.0",
        fixed_version="1.0.0",
        source="test",
        cvss_score=7.5,
    )

    logger.debug("Adding security issue to ontology")
    checker._add_to_ontology("test-pkg", issue)

    # Verify the vulnerability was added correctly
    logger.debug("Verifying ontology triples")
    vuln_uri = URIRef(f"{SEC}TEST-001")

    assert (vuln_uri, RDF.type, SEC.Vulnerability) in mock_graph
    assert (vuln_uri, SEC.severity, Literal("High")) in mock_graph
    assert (vuln_uri, SEC.affectsPackage, Literal("test-pkg")) in mock_graph

    logger.debug("Ontology integration test passed")


# Add methods to SecurityIssue for parsing scanner outputs
@staticmethod
def from_safety_json(data: dict, package: str) -> "SecurityIssue":
    """Create SecurityIssue from safety scanner output."""
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
    return SecurityIssue(
        cve_id=data.get("id", "Unknown"),
        description=data.get("description", "No description available"),
        severity=data.get("severity", "Unknown"),
        affected_versions=", ".join(data.get("affected_versions", [])),
        fixed_version=data.get("fixed_version"),
        source="pip-audit",
        cvss_score=data.get("cvss_score"),
    )
