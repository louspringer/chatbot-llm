"""
Tests for the package management script.
"""

import tempfile
from pathlib import Path
from unittest.mock import patch

import pytest
from rdflib import Graph, Literal, Namespace
from rdflib.namespace import RDF, RDFS

from scripts.manage_packages import PackageManager


@pytest.fixture
def temp_workspace():
    """Creates a temporary workspace for testing."""
    with tempfile.TemporaryDirectory() as temp_dir:
        workspace = Path(temp_dir)

        # Create test files
        (workspace / "pyproject.toml").write_text(
            """
[project]
name = "test-project"
version = "0.1.0"
dependencies = []

[project.optional-dependencies]
dev = []
"""
        )

        (workspace / "environment.yml").write_text(
            """
name: test-env
channels:
  - conda-forge
  - defaults
dependencies: []
"""
        )

        # Create test ontology
        pkg = Namespace("file://package_management#")
        graph = Graph()
        graph.bind("pkg", pkg)

        # Add dependency types
        for dep_type in ["CoreDependency", "DevelopmentDependency"]:
            graph.add((pkg[dep_type], RDF.type, pkg.DependencyType))
            graph.add((pkg[dep_type], RDFS.label, Literal(dep_type)))

        graph.serialize(workspace / "package_management.ttl", format="turtle")

        yield workspace


@pytest.fixture
def package_manager(temp_workspace):
    """Creates a PackageManager instance for testing."""
    return PackageManager(temp_workspace)


def test_validate_package_request(package_manager):
    """Tests package request validation."""
    # Test valid core dependency
    assert package_manager.validate_package_request(
        "test-package", "1.0.0", "CoreDependency"
    )

    # Test valid development dependency
    assert package_manager.validate_package_request(
        "test-package", "1.0.0", "DevelopmentDependency"
    )

    # Test invalid dependency type
    assert not package_manager.validate_package_request(
        "test-package", "1.0.0", "InvalidDependency"
    )

    # Test duplicate package
    package_manager._update_ontology("test-package", "1.0.0", "CoreDependency")
    assert not package_manager.validate_package_request(
        "test-package", "2.0.0", "CoreDependency"
    )


@patch("subprocess.run")
def test_add_conda_package(mock_run, package_manager):
    """Tests adding a package via conda."""
    package_manager._add_conda_package("test-package", "1.0.0")

    # Check environment.yml was updated
    with open(package_manager.environment_yml_path) as f:
        content = f.read()
        assert "test-package=1.0.0" in content

    # Check conda command was called
    mock_run.assert_called_once_with(
        [
            "conda",
            "env",
            "update",
            "-f",
            str(package_manager.environment_yml_path),
        ],
        check=True,
    )


@patch("subprocess.run")
def test_add_pip_package(mock_run, package_manager):
    """Tests adding a package via pip."""
    package_manager._add_pip_package("test-package", "1.0.0", "CoreDependency")

    # Check pyproject.toml was updated
    with open(package_manager.pyproject_path) as f:
        content = f.read()
        assert "test-package>=1.0.0" in content

    # Check pip command was called
    mock_run.assert_called_once_with(["pip", "install", "-e", "."], check=True)


@patch("subprocess.run")
def test_add_package(mock_run, package_manager):
    """Tests the complete package addition process."""
    # Test successful conda package addition
    assert package_manager.add_package(
        "test-package", "1.0.0", "CoreDependency", use_conda=True
    )

    # Check ontology was updated
    assert package_manager._package_exists("test-package")

    # Test failed package addition (duplicate)
    assert not package_manager.add_package(
        "test-package", "2.0.0", "CoreDependency", use_conda=True
    )

    # Test failed package addition (invalid type)
    assert not package_manager.add_package(
        "other-package", "1.0.0", "InvalidDependency", use_conda=True
    )


def test_package_exists(package_manager):
    """Tests package existence check."""
    assert not package_manager._package_exists("test-package")

    package_manager._update_ontology("test-package", "1.0.0", "CoreDependency")
    assert package_manager._package_exists("test-package")
