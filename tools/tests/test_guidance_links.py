"""Tests for guidance_links.py.

Traceability:
    - Ontology: test.ttl
    - Class: test:GuidanceLinksTest
    - Requirement: REQ-TEST-002 Guidance Links Testing
    - Guidance: guidance:TestingGuidelines
    - Description: Tests for symbolic link management in the guidance module
"""

from pathlib import Path
from unittest.mock import MagicMock, patch

import pytest

from ..guidance_links import (
    create_module_symlinks,
    ensure_symlink,
    extract_module_paths,
    main,
)


@pytest.fixture
def mock_ttl_content():
    """Sample TTL content with module imports."""
    return """
    @prefix owl: <http://www.w3.org/2002/07/owl#> .
    @prefix rdf: <http://www.w3.org/1999/02/22-rdf-syntax-ns#> .

    :GuidanceOntology rdf:type owl:Ontology ;
        owl:imports <./guidance/modules/core.ttl> ;
        owl:imports <./guidance/modules/model.ttl> ;
        owl:imports <./guidance/modules/security.ttl> .
    """


def test_extract_module_paths(tmp_path, mock_ttl_content):
    """Test extracting module paths from TTL file."""
    ttl_file = tmp_path / "guidance.ttl"
    ttl_file.write_text(mock_ttl_content)

    modules = extract_module_paths(ttl_file)

    assert len(modules) == 3
    assert modules["core"] == "guidance/modules/core.ttl"
    assert modules["model"] == "guidance/modules/model.ttl"
    assert modules["security"] == "guidance/modules/security.ttl"


def test_extract_module_paths_file_not_found():
    """Test handling of missing TTL file."""
    with pytest.raises(FileNotFoundError):
        extract_module_paths(Path("nonexistent.ttl"))


def test_extract_module_paths_no_imports(tmp_path):
    """Test handling of TTL file with no imports."""
    ttl_file = tmp_path / "empty.ttl"
    ttl_file.write_text("@prefix owl: <http://www.w3.org/2002/07/owl#> .")

    with pytest.raises(ValueError, match="No module imports found"):
        extract_module_paths(ttl_file)


def test_ensure_symlink():
    """Test symlink creation."""
    source = MagicMock(spec=Path)
    target = MagicMock(spec=Path)

    # Mock file existence checks - source exists but target doesn't
    source.exists.return_value = True
    target.exists.return_value = False
    target.is_symlink.return_value = False

    ensure_symlink(source, target)

    target.symlink_to.assert_called_once()


@patch("pathlib.Path.symlink_to")
@patch("pathlib.Path.exists")
def test_ensure_symlink_source_not_found(mock_exists, mock_symlink_to):
    """Test handling of missing source file."""
    source = Path("/source/file.ttl")
    target = Path("/target/file.ttl")

    mock_exists.return_value = False

    with pytest.raises(FileNotFoundError):
        ensure_symlink(source, target)

    mock_symlink_to.assert_not_called()


@patch("tools.guidance_links.ensure_symlink")
@patch("pathlib.Path.exists")
@patch("pathlib.Path.glob")
def test_create_module_symlinks(mock_glob, mock_exists, mock_ensure_symlink):
    """Test creation of module symlinks."""
    source_dir = Path("/source")
    target_dir = Path("/target")
    modules = {
        "core": "guidance/modules/core.ttl",
        "model": "guidance/modules/model.ttl",
    }

    # Mock directory existence
    mock_exists.return_value = True
    mock_glob.return_value = [
        Path("/source/guidance/modules/core.ttl"),
        Path("/source/guidance/modules/model.ttl"),
    ]

    create_module_symlinks(source_dir, target_dir, modules)

    assert mock_ensure_symlink.call_count == 2


@patch("tools.guidance_links.create_module_symlinks")
@patch("tools.guidance_links.extract_module_paths")
@patch("pathlib.Path.exists")
def test_main_success(mock_exists, mock_extract, mock_create):
    """Test successful execution of main function."""
    mock_exists.return_value = True
    mock_extract.return_value = {
        "core": "guidance/modules/core.ttl",
        "model": "guidance/modules/model.ttl",
    }

    result = main(Path("/project"))

    assert result == 0
    mock_create.assert_called_once()


@patch("pathlib.Path.exists")
def test_main_missing_framework_dir(mock_exists):
    """Test handling of missing ontology-framework directory."""
    mock_exists.return_value = False

    result = main(Path("/project"))

    assert result == 1
