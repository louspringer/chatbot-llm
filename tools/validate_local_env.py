"""
Local environment validator for checking required tools and configurations.
"""

import json
import logging
import re
import subprocess
from dataclasses import dataclass
from datetime import datetime
from pathlib import Path
from typing import Dict, List, Optional, Set, Tuple

from rdflib import Graph, URIRef

# Setup logging
logger = logging.getLogger(__name__)


@dataclass
class ValidationResult:
    """Result of a validation check with impact information."""

    success: bool
    message: str
    details: str = ""  # Make details optional with default empty string
    impact_level: Optional[str] = None
    requires_revalidation: bool = False


@dataclass
class ConfigurationState:
    """State of configuration files for drift detection."""

    content_hash: str
    timestamp: datetime
    validator: str
    drift_threshold: float


@dataclass
class ImpactAnalysis:
    """Analysis of impact from configuration changes."""

    affected_artifacts: Set[str]
    impact_level: str
    validation_required: bool


@dataclass
class StateInfo:
    baseline: str
    drift_threshold: float


@dataclass
class OwnershipInfo:
    """Ownership information extracted from file headers."""

    owner: str
    version: str
    purpose: str
    ontology: str


class LocalEnvValidator:
    """Validates local environment setup and configuration."""

    def __init__(self, workspace_root: Path):
        """Initialize validator with workspace root."""
        self.workspace_root = workspace_root
        self.state_cache: Dict[str, StateInfo] = {}
        self.required_files = {
            "environment.yml": 0.1,
            "pyproject.toml": 0.2,
            ".env.template": 0.1,
            ".gitignore": 0.3,
        }
        self.graph: Optional[Graph] = None

        # Define required tools with impact levels
        self.required_tools = {
            "op": {
                "description": "1Password CLI",
                "impact_level": "HIGH",
                "install_instructions": {
                    "all": "https://1password.com/downloads/command-line/"
                },
            },
            "ngrok": {
                "description": "ngrok tunneling",
                "impact_level": "MEDIUM",
                "install_instructions": {"all": "https://ngrok.com/download"},
            },
            "conda": {
                "description": "Conda package manager",
                "impact_level": "HIGH",
                "install_instructions": {
                    "all": (
                        "https://docs.conda.io/projects/conda/en/latest"
                        "/user-guide/install/"
                    )
                },
            },
            "git": {
                "description": "Git version control",
                "impact_level": "HIGH",
                "install_instructions": {
                    "all": "https://git-scm.com/downloads"
                },
            },
        }

    def validate_tool(self, tool: str, tool_info: Dict) -> ValidationResult:
        """Validate if a required tool is installed and accessible."""
        try:
            if tool == "op":
                return self.validate_1password()

            result = subprocess.run(
                [tool, "--version"],
                capture_output=True,
                text=True,
                check=True,
            )
            return ValidationResult(
                success=True,
                message=f"✅ {tool} is installed",
                details=result.stdout.strip(),
                impact_level=tool_info["impact_level"],
            )
        except (FileNotFoundError, subprocess.CalledProcessError):
            install_url = tool_info["install_instructions"]["all"]
            return ValidationResult(
                success=False,
                message=f"❌ {tool} is not installed",
                details=f"Install instructions: {install_url}",
                impact_level=tool_info["impact_level"],
            )

    def validate_1password(self) -> ValidationResult:
        """Validate 1Password CLI authentication."""
        try:
            result = subprocess.run(
                ["op", "whoami"],
                capture_output=True,
                text=True,
                check=True,
            )
            if result.stdout.strip():
                user = result.stdout.strip()
                return ValidationResult(
                    success=True,
                    message="✅ 1Password CLI authenticated",
                    details=f"Authenticated as {user}",
                    impact_level="HIGH",
                )
            return ValidationResult(
                success=False,
                message="❌ 1Password CLI not authenticated",
                details="Run 'op signin' to authenticate",
                impact_level="HIGH",
            )
        except (FileNotFoundError, subprocess.CalledProcessError):
            msg = "❌ 1Password CLI not installed or not authenticated"
            return ValidationResult(
                success=False,
                message=msg,
                details="Install 1Password CLI and run 'op signin'",
                impact_level="HIGH",
            )

    def validate_conda_env(self) -> ValidationResult:
        """Validate conda environment setup."""
        env_file = self.workspace_root / "environment.yml"
        if not env_file.exists():
            return ValidationResult(
                success=False,
                message="❌ environment.yml not found",
                details="Create environment.yml file",
                impact_level="HIGH",
            )

        try:
            result = subprocess.run(
                ["conda", "env", "list", "--json"],
                capture_output=True,
                text=True,
                check=True,
            )
            envs = json.loads(result.stdout)["envs"]
            env_name = "chatbot-llm"

            if any(env_name in env for env in envs):
                msg = f"✅ Conda environment '{env_name}' exists"
                return ValidationResult(
                    success=True,
                    message=msg,
                    details="Environment is properly configured",
                    impact_level="HIGH",
                )
            msg = f"❌ Conda environment '{env_name}' not found"
            return ValidationResult(
                success=False,
                message=msg,
                details="Run 'conda env create -f environment.yml'",
                impact_level="HIGH",
            )
        except (subprocess.CalledProcessError, json.JSONDecodeError):
            return ValidationResult(
                success=False,
                message="❌ Error checking conda environment",
                details="Ensure conda is installed and working properly",
                impact_level="HIGH",
            )

    def validate_git_config(self) -> ValidationResult:
        """Validate git configuration."""
        try:
            email = subprocess.run(
                ["git", "config", "user.email"],
                capture_output=True,
                text=True,
                check=True,
            ).stdout.strip()
            name = subprocess.run(
                ["git", "config", "user.name"],
                capture_output=True,
                text=True,
                check=True,
            ).stdout.strip()

            if email and name:
                details = f"Configured for {name} <{email}>"
                return ValidationResult(
                    success=True,
                    message="✅ Git config is valid",
                    details=details,
                    impact_level="HIGH",
                )
            return ValidationResult(
                success=False,
                message="❌ Git config is incomplete",
                details="Set git config user.name and user.email",
                impact_level="HIGH",
            )
        except subprocess.CalledProcessError:
            return ValidationResult(
                success=False,
                message="❌ Git config error",
                details="Error reading git configuration",
                impact_level="HIGH",
            )

    def detect_configuration_drift(
        self, file_path: Path, drift_threshold: float
    ) -> Tuple[bool, float]:
        """Detect configuration drift by comparing with baseline."""
        content = file_path.read_text()
        state_key = file_path.name

        if state_key not in self.state_cache:
            self.state_cache[state_key] = StateInfo(content, drift_threshold)
            return False, 0.0

        baseline = self.state_cache[state_key].baseline
        if baseline != content:
            # Calculate diff percentage
            baseline_words = set(baseline.split())
            current_words = set(content.split())
            changes = len(baseline_words.symmetric_difference(current_words))
            total = len(baseline_words.union(current_words))
            drift_pct = changes / total if total > 0 else 0
            return drift_pct > drift_threshold, drift_pct
        return False, 0.0

    def analyze_impact(self, artifact: str) -> List[str]:
        """Analyze impact of changes to an artifact."""
        if not self.graph:
            return []
        impacted = []
        # Convert string to URIRef for RDFLib compatibility
        artifact_uri = URIRef(artifact)
        for _, _, target in self.graph.triples((None, None, artifact_uri)):
            impacted.append(str(target))
        return impacted

    def extract_ownership_info(
        self, file_path: Path
    ) -> Optional[OwnershipInfo]:
        """Extract ownership information from file header."""
        if not file_path.exists():
            return None

        content = file_path.read_text()
        owner_match = re.search(r"# Owned by: (.*)", content)
        version_match = re.search(r"# Version: (.*)", content)
        purpose_match = re.search(r"# Purpose: (.*)", content)

        if not (owner_match and version_match and purpose_match):
            return None

        owner = owner_match.group(1).strip()
        is_meta = owner.startswith("meta:")
        ontology = "meta:EnvironmentConfigOntology" if is_meta else owner

        return OwnershipInfo(
            owner=owner,
            version=version_match.group(1).strip(),
            purpose=purpose_match.group(1).strip(),
            ontology=ontology,
        )

    def validate_required_files(self) -> List[ValidationResult]:
        """Validate required files and their ownership information."""
        results = []
        for fname, threshold in self.required_files.items():
            fpath = self.workspace_root / fname
            if not fpath.exists():
                msg = f"❌ Missing required file: {fname}"
                results.append(
                    ValidationResult(False, msg, impact_level="HIGH")
                )
                continue

            ownership = self.extract_ownership_info(fpath)
            if not ownership:
                msg = f"❌ Missing ownership metadata in {fname}"
                results.append(
                    ValidationResult(False, msg, impact_level="MEDIUM")
                )
                continue

            has_drifted, drift_pct = self.detect_configuration_drift(
                fpath, threshold
            )
            if has_drifted:
                msg_parts = [
                    "❌ Configuration drift detected in",
                    fname,
                    f"({drift_pct:.1%})",
                ]
                drift_msg = " ".join(msg_parts)
                results.append(
                    ValidationResult(
                        success=False,
                        message=drift_msg,
                        impact_level="HIGH",
                        requires_revalidation=True,
                    )
                )
            else:
                msg = f"✅ {fname} validated successfully"
                results.append(ValidationResult(True, msg))

        return results

    def validate_ownership(self, file_path: Path) -> ValidationResult:
        """Validate ownership information in a file."""
        ownership = self.extract_ownership_info(file_path)
        if not ownership:
            msg = "File header must include ownership metadata"
            return ValidationResult(
                success=False,
                message="❌ Missing ownership information",
                details=msg,
                impact_level="HIGH",
            )

        # Validate against required files if applicable
        fname = file_path.name
        if fname in self.required_files:
            # Convert owner to string for comparison
            expected = str(self.required_files[fname])
            if ownership.owner != expected:
                msg_parts = [
                    "Expected owner:",
                    str(expected),
                    "Found:",
                    ownership.owner,
                ]
                details = " ".join(msg_parts)
                return ValidationResult(
                    success=False,
                    message="❌ Invalid ownership",
                    details=details,
                    impact_level="HIGH",
                )

        owner_info = f"Owner: {ownership.owner}"
        version_info = f"Version: {ownership.version}"
        details = f"{owner_info}, {version_info}"

        return ValidationResult(
            success=True,
            message="✅ Valid ownership information",
            details=details,
            impact_level="HIGH",
        )

    def run_validation(self) -> List[ValidationResult]:
        """Run all validation checks and return validation results."""
        results = []

        # Validate tools
        for tool, info in self.required_tools.items():
            results.append(self.validate_tool(tool, info))

        # Validate conda environment
        results.append(self.validate_conda_env())

        # Validate git config
        results.append(self.validate_git_config())

        # Validate required files
        results.extend(self.validate_required_files())

        return results
