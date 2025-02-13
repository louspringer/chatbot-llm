"""
Tests for the local environment validator
"""

from datetime import datetime
from typing import Dict
from unittest.mock import MagicMock, patch

import pytest

from tools.validate_local_env import (
    ConfigurationState,
    ImpactAnalysis,
    LocalEnvValidator,
    OwnershipInfo,
    ValidationResult,
)


@pytest.fixture
def validator(tmp_path):
    with patch("logging.getLogger"):
        validator = LocalEnvValidator(workspace_root=tmp_path)
        yield validator


@pytest.fixture
def mock_env_file(tmp_path):
    env_file = tmp_path / ".env.template"
    env_content = """
# Owned by: meta:EnvironmentConfigOntology
# Version: 1.0.0
# Purpose: Template for environment variables

TEAMS_BOT_ID=
TEAMS_BOT_PASSWORD=
DEBUG=true
"""
    env_file.write_text(env_content)
    return env_file


def test_validation_result():
    """Test ValidationResult dataclass with impact information"""
    result = ValidationResult(
        True,
        "Success",
        "Details",
        impact_level="HIGH",
        requires_revalidation=True,
    )
    assert result.success
    assert result.message == "Success"
    assert result.details == "Details"
    assert result.impact_level == "HIGH"
    assert result.requires_revalidation


def test_configuration_state():
    """Test ConfigurationState dataclass"""
    state = ConfigurationState(
        content_hash="abc123",
        timestamp=datetime.now(),
        validator="test-validator",
        drift_threshold=0.1,
    )
    assert state.content_hash == "abc123"
    assert state.validator == "test-validator"
    assert state.drift_threshold == 0.1


def test_impact_analysis():
    """Test ImpactAnalysis dataclass"""
    impact = ImpactAnalysis(
        affected_artifacts={"env", "config"},
        impact_level="HIGH",
        validation_required=True,
    )
    assert "env" in impact.affected_artifacts
    assert impact.impact_level == "HIGH"
    assert impact.validation_required


@pytest.mark.parametrize(
    "tool,version_output,impact_level",
    [
        ("op", "1Password CLI 2.0.0", "HIGH"),
        ("ngrok", "ngrok version 3.0.0", "MEDIUM"),
        ("conda", "conda 4.10.0", "HIGH"),
        ("git", "git version 2.30.0", "HIGH"),
    ],
)
def test_validate_tool_success(validator, tool, version_output, impact_level):
    """Test tool validation with impact levels"""
    with patch("subprocess.run") as mock_run:
        mock_run.return_value = MagicMock(
            stdout=version_output, stderr="", returncode=0
        )
        tool_info = {
            "description": "test tool",
            "impact_level": impact_level,
            "install_instructions": {"all": "test"},
        }
        result = validator.validate_tool(tool, tool_info)
        assert result.success
        assert "✅" in result.message
        assert version_output in result.details
        assert result.impact_level == impact_level


def test_validate_tool_not_found(validator):
    """Test tool validation when tool is missing"""
    with patch("subprocess.run") as mock_run:
        mock_run.side_effect = FileNotFoundError()
        tool_info = {
            "description": "test tool",
            "impact_level": "HIGH",
            "install_instructions": {"all": "test"},
        }
        result = validator.validate_tool("missing-tool", tool_info)
        assert not result.success
        assert "❌" in result.message


def test_validate_1password_authenticated(validator):
    """Test 1Password validation when authenticated"""
    with patch("subprocess.run") as mock_run:
        mock_run.return_value = MagicMock(
            stdout="example@email.com", stderr="", returncode=0
        )
        result = validator.validate_1password()
        assert result.success
        assert "✅" in result.message


def test_validate_1password_not_authenticated(validator):
    """Test 1Password validation when not authenticated"""
    with patch("subprocess.run") as mock_run:
        mock_run.return_value = MagicMock(stdout="", stderr="", returncode=0)
        result = validator.validate_1password()
        assert not result.success
        assert "❌" in result.message
        assert "op signin" in result.details


def test_validate_conda_env_exists(validator, tmp_path):
    """Test conda environment validation when environment exists"""
    env_file = tmp_path / "environment.yml"
    env_file.write_text(
        """
name: chatbot-llm
channels:
  - conda-forge
dependencies:
  - python=3.10
"""
    )

    with patch("subprocess.run") as mock_run:
        mock_run.return_value = MagicMock(
            stdout='{"envs": ["/path/to/chatbot-llm"]}',
            stderr="",
            returncode=0,
        )
        with patch.object(validator, "workspace_root", tmp_path):
            result = validator.validate_conda_env()
            assert result.success
            assert "✅" in result.message


def test_validate_conda_env_missing(validator, tmp_path):
    """Test conda environment validation when environment is missing"""
    env_file = tmp_path / "environment.yml"
    env_file.write_text(
        """
name: chatbot-llm
channels:
  - conda-forge
dependencies:
  - python=3.10
"""
    )

    with patch("subprocess.run") as mock_run:
        mock_run.return_value = MagicMock(
            stdout='{"envs": []}', stderr="", returncode=0
        )
        with patch.object(validator, "workspace_root", tmp_path):
            result = validator.validate_conda_env()
            assert not result.success
            assert "❌" in result.message
            assert "conda env create" in result.details


def test_validate_git_config_valid(validator):
    """Test git config validation with valid config"""
    with patch("subprocess.run") as mock_run:

        def mock_git_config(*args, **kwargs):
            if "user.email" in args[0]:
                return MagicMock(stdout="user@example.com\n", stderr="")
            elif "user.name" in args[0]:
                return MagicMock(stdout="Test User\n", stderr="")
            return MagicMock(stdout="", stderr="")

        mock_run.side_effect = mock_git_config
        result = validator.validate_git_config()
        assert result.success
        assert "✅" in result.message
        assert "user@example.com" in result.details


def test_validate_git_config_invalid(validator):
    """Test git config validation with missing config"""
    with patch("subprocess.run") as mock_run:
        mock_run.return_value = MagicMock(stdout="", stderr="")
        result = validator.validate_git_config()
        assert not result.success
        assert "❌" in result.message


def test_validate_required_files_all_present(validator, tmp_path):
    """Test required files validation when all files exist"""
    # Create test files with ownership info
    for filename, owner in validator.required_files.items():
        file_path = tmp_path / filename
        file_path.write_text(
            f"""
# Owned by: {owner}
# Version: 1.0.0
# Purpose: Test file
"""
        )

    with patch.object(validator, "workspace_root", tmp_path):
        results = validator.validate_required_files()
        assert all(r.success for r in results)


def test_validate_required_files_missing(validator, tmp_path):
    """Test required files validation when files are missing"""
    with patch.object(validator, "workspace_root", tmp_path):
        results = validator.validate_required_files()
        assert not any(r.success for r in results)
        assert all("❌" in r.message for r in results)


def test_run_validation_all_pass(validator):
    """Test full validation when everything passes"""
    success_result = ValidationResult(True, "✅")
    with patch.multiple(
        validator,
        validate_tool=MagicMock(return_value=success_result),
        validate_1password=MagicMock(return_value=success_result),
        validate_conda_env=MagicMock(return_value=success_result),
        validate_git_config=MagicMock(return_value=success_result),
        validate_required_files=MagicMock(return_value=[success_result]),
    ):
        assert validator.run_validation()


def test_run_validation_with_failures(validator):
    """Test full validation when some checks fail"""
    success_result = ValidationResult(True, "✅")
    failure_result = ValidationResult(False, "❌")
    with patch.multiple(
        validator,
        validate_tool=MagicMock(return_value=failure_result),
        validate_1password=MagicMock(return_value=success_result),
        validate_conda_env=MagicMock(return_value=failure_result),
        validate_git_config=MagicMock(return_value=success_result),
        validate_required_files=MagicMock(return_value=[failure_result]),
    ):
        results = validator.run_validation()
        assert any(not r.success for r in results)


def test_detect_configuration_drift_no_baseline(validator, tmp_path):
    """Test drift detection with no baseline"""
    test_file = tmp_path / "test.yml"
    test_file.write_text("test: value")

    with patch.object(validator, "workspace_root", tmp_path):
        drift_result = validator.detect_configuration_drift(test_file, 0.1)
        has_drifted, drift_pct = drift_result
        assert not has_drifted
        assert drift_pct == 0.0

        # Verify state was cached
        state_key = "test.yml"
        assert state_key in validator.state_cache
        assert validator.state_cache[state_key].drift_threshold == 0.1


def test_detect_configuration_drift_with_changes(validator, tmp_path):
    """Test drift detection when file changes"""
    test_file = tmp_path / "test.yml"
    test_file.write_text("key: value1\nother: test1")

    with patch.object(validator, "workspace_root", tmp_path):
        # Create baseline
        validator.detect_configuration_drift(test_file, 0.1)

        # Modify file with significant changes
        test_file.write_text("key: value2\nother: test2")

        drift_result = validator.detect_configuration_drift(test_file, 0.1)
        has_drifted, drift_pct = drift_result
        assert has_drifted
        assert drift_pct > 0.1


def test_analyze_impact_from_ontology(validator):
    """Test impact analysis using ontology data"""
    with patch.object(validator, "graph") as mock_graph:
        # Mock ontology queries
        mock_graph.triples.return_value = [
            (None, None, "artifact1"),
            (None, None, "artifact2"),
        ]

        impacted = validator.analyze_impact("test_artifact")
        assert len(impacted) == 2
        assert "artifact1" in impacted
        assert "artifact2" in impacted


def test_validate_ownership_valid(validator, mock_env_file):
    """Test ownership validation with valid metadata"""
    # Update required files with string values
    validator.required_files = {
        ".env.template": "meta:EnvironmentConfigOntology",
        "pyproject.toml": "meta:CoreOntology",
    }

    result = validator.validate_ownership(mock_env_file)
    assert result.success
    assert "✅" in result.message
    assert "meta:EnvironmentConfigOntology" in result.details


def test_validate_ownership_missing(validator, tmp_path):
    """Test ownership validation with missing metadata"""
    invalid_file = tmp_path / "invalid.yml"
    invalid_file.write_text("test: value")

    result = validator.validate_ownership(invalid_file)
    assert not result.success
    assert "❌" in result.message


def test_validate_required_files_with_drift(validator, tmp_path):
    """Test required files validation with drift detection"""
    # Update required files with string values
    validator.required_files = {
        "environment.yml": "meta:CoreOntology",
        "pyproject.toml": "meta:CoreOntology",
    }

    test_file = tmp_path / "environment.yml"
    test_file.write_text(
        """
# Owned by: meta:CoreOntology
# Version: 1.0.0
# Purpose: Test environment file
name: test-env
dependencies:
  - python=3.11
"""
    )

    with patch.object(validator, "workspace_root", tmp_path):
        # First validation establishes baseline
        results = validator.validate_required_files()
        success_condition = [
            r.success and "environment.yml" in r.message for r in results
        ]
        assert any(success_condition)

        # Modify file to trigger drift
        test_file.write_text(
            """
# Owned by: meta:CoreOntology
# Version: 1.0.0
# Purpose: Test environment file
name: modified-env
dependencies:
  - python=3.12
"""
        )
        results = validator.validate_required_files()

        def has_drift_message(result):
            has_failed = not result.success
            has_drift = "drift detected" in result.message.lower()
            return has_failed and has_drift

        assert any(has_drift_message(r) for r in results)


def test_run_validation_with_revalidation(validator):
    """Test full validation with revalidation tracking"""
    success_result = ValidationResult(True, "✅", requires_revalidation=False)
    failure_result = ValidationResult(
        False, "❌", requires_revalidation=True, impact_level="HIGH"
    )

    def mock_validate_tool(tool: str, tool_info: Dict) -> ValidationResult:
        if tool in ["op", "conda"]:
            return failure_result
        return success_result

    with patch.multiple(
        validator,
        validate_tool=MagicMock(side_effect=mock_validate_tool),
        validate_1password=MagicMock(return_value=success_result),
        validate_conda_env=MagicMock(return_value=failure_result),
        validate_git_config=MagicMock(return_value=success_result),
        validate_required_files=MagicMock(return_value=[failure_result]),
    ):
        results = validator.run_validation()
        # Check that we have at least one failure
        assert any(not r.success for r in results)
        # Check that we have at least one result requiring revalidation
        assert any(r.requires_revalidation for r in results)


def test_extract_ownership_info_valid(validator, mock_env_file):
    """Test ownership info extraction with valid metadata"""
    info = validator.extract_ownership_info(mock_env_file)
    assert isinstance(info, OwnershipInfo)
    assert info.ontology == "meta:EnvironmentConfigOntology"
    assert info.version == "1.0.0"


def test_extract_ownership_info_invalid(validator, tmp_path):
    """Test ownership info extraction with invalid metadata"""
    invalid_file = tmp_path / "invalid.yml"
    invalid_file.write_text("test: value")

    info = validator.extract_ownership_info(invalid_file)
    assert info is None


@pytest.mark.parametrize(
    "file_type,drift_threshold",
    [
        ("environment.yml", 0.1),
        ("pyproject.toml", 0.2),
        (".env.template", 0.1),
        (".gitignore", 0.3),
    ],
)
def test_file_specific_drift_thresholds(
    validator, tmp_path, file_type, drift_threshold
):
    """Test drift thresholds for different file types"""
    test_file = tmp_path / file_type
    test_file.write_text("initial content")

    with patch.object(validator, "workspace_root", tmp_path):
        # First validation establishes baseline
        validator.detect_configuration_drift(test_file, drift_threshold)

        # Verify correct threshold was used
        state_key = file_type
        threshold = validator.state_cache[state_key].drift_threshold
        assert threshold == drift_threshold
