#!/usr/bin/env python3

"""
Local Environment Validator

Validates and ensures proper setup of the local development environment.
Checks for required tools, configurations, proper authentication,
ownership metadata, and performs impact analysis and drift detection.
"""

import json
import logging
import subprocess
import sys
import hashlib
from dataclasses import dataclass
from datetime import datetime
from pathlib import Path
from typing import Dict, List, Optional, Set, Tuple

import yaml
from rdflib import Graph, Namespace, URIRef
from rdflib.namespace import RDF, RDFS


@dataclass
class ValidationResult:
    success: bool
    message: str
    details: Optional[str] = None
    impact_level: Optional[str] = None
    requires_revalidation: bool = False


@dataclass
class OwnershipInfo:
    ontology: str
    version: str
    purpose: str


@dataclass
class ConfigurationState:
    content_hash: str
    timestamp: datetime
    validator: str
    drift_threshold: float = 0.1


@dataclass
class ImpactAnalysis:
    affected_artifacts: Set[str]
    impact_level: str
    validation_required: bool


class LocalEnvValidator:
    def __init__(self):
        self.workspace_root = Path(__file__).parent.parent
        self.setup_logging()
        self.load_ontology()

        # Required tools and their descriptions
        self.required_tools = {
            "op": {
                "description": "1Password CLI for secrets management",
                "impact_level": "HIGH",
                "install_instructions": {
                    "darwin": "brew install 1password-cli",
                    "linux": "https://developer.1password.com/docs/cli/get-started/",
                    "win32": "https://developer.1password.com/docs/cli/get-started/",
                },
            },
            "ngrok": {
                "description": "ngrok for Teams endpoints",
                "impact_level": "MEDIUM",
                "install_instructions": {
                    "darwin": "brew install ngrok",
                    "linux": "snap install ngrok",
                    "win32": "choco install ngrok",
                },
            },
            "conda": {
                "description": "Conda for environment management",
                "impact_level": "HIGH",
                "install_instructions": {
                    "all": "https://docs.conda.io/en/latest/miniconda.html",
                },
            },
            "git": {
                "description": "Git for version control",
                "impact_level": "HIGH",
                "install_instructions": {
                    "darwin": "brew install git",
                    "linux": "apt-get install git",
                    "win32": "https://git-scm.com/download/win",
                },
            },
        }

        # Required files and their purposes
        self.required_files = {
            "environment.yml": {
                "purpose": "Conda environment configuration",
                "impact_level": "HIGH",
                "drift_threshold": 0.1,
            },
            "pyproject.toml": {
                "purpose": "Python project configuration",
                "impact_level": "MEDIUM",
                "drift_threshold": 0.2,
            },
            ".env.template": {
                "purpose": "Environment variables template",
                "impact_level": "HIGH",
                "drift_threshold": 0.1,
            },
            ".gitignore": {
                "purpose": "Git ignore patterns",
                "impact_level": "LOW",
                "drift_threshold": 0.3,
            },
        }

        # Configuration state cache
        self.state_cache = {}

    def setup_logging(self):
        """Configure logging for the validator"""
        log_dir = self.workspace_root / "logs"
        log_dir.mkdir(exist_ok=True)

        logging.basicConfig(
            level=logging.INFO,
            format="%(asctime)s - %(levelname)s - %(message)s",
            handlers=[
                logging.StreamHandler(),
                logging.FileHandler(log_dir / "env_validation.log"),
            ],
        )
        self.logger = logging.getLogger(__name__)

    def load_ontology(self):
        """Load the environment configuration ontology"""
        self.graph = Graph()
        ontology_path = self.workspace_root / "environment_config.ttl"
        if ontology_path.exists():
            self.graph.parse(ontology_path, format="turtle")
            self.logger.info("Loaded environment configuration ontology")
        else:
            self.logger.warning("Environment configuration ontology not found")

    def calculate_file_hash(self, file_path: Path) -> str:
        """Calculate SHA-256 hash of file contents"""
        if not file_path.exists():
            return ""
        
        sha256_hash = hashlib.sha256()
        with open(file_path, "rb") as f:
            for byte_block in iter(lambda: f.read(4096), b""):
                sha256_hash.update(byte_block)
        return sha256_hash.hexdigest()

    def detect_configuration_drift(
        self, file_path: Path, threshold: float
    ) -> Tuple[bool, float]:
        """
        Detect if configuration has drifted beyond threshold
        Returns (has_drifted, drift_percentage)
        """
        current_hash = self.calculate_file_hash(file_path)
        if not current_hash:
            return True, 1.0

        state_key = file_path.name
        baseline = self.state_cache.get(state_key)
        
        if not baseline:
            # No baseline, store current state
            self.state_cache[state_key] = ConfigurationState(
                content_hash=current_hash,
                timestamp=datetime.now(),
                validator="environment-validator",
                drift_threshold=threshold
            )
            return False, 0.0

        if current_hash != baseline.content_hash:
            # Simple hash comparison for now
            # Could be enhanced with semantic diff
            return True, 1.0

        return False, 0.0

    def analyze_impact(
        self, artifact: str, change_type: str
    ) -> ImpactAnalysis:
        """Analyze impact of changes to an artifact"""
        affected = set()
        impact_level = "LOW"
        requires_validation = False

        # Check ontology for dependencies
        if self.graph:
            envconfig = Namespace("./environment_config#")
            artifact_uri = URIRef(f"./environment_config#{artifact}")
            
            # Find artifacts impacted by this one
            for _, _, impacted in self.graph.triples(
                (artifact_uri, envconfig.impactsArtifact, None)
            ):
                affected.add(str(impacted))

            # Get impact level
            for _, _, level in self.graph.triples(
                (artifact_uri, envconfig.hasImpactLevel, None)
            ):
                impact_level = str(level).split("#")[-1].upper()

            # Check if revalidation is required
            for _, _, required in self.graph.triples(
                (artifact_uri, envconfig.requiresRevalidation, None)
            ):
                requires_validation = bool(required)

        return ImpactAnalysis(affected, impact_level, requires_validation)

    def get_install_instructions(self, tool: str) -> str:
        """Get platform-specific installation instructions for a tool"""
        if tool not in self.required_tools:
            return "No installation instructions available"
            
        instructions = self.required_tools[tool]["install_instructions"]
        platform = sys.platform

        if "all" in instructions:
            return f"Install from: {instructions['all']}"
        elif platform in instructions:
            return f"Run: {instructions[platform]}"
        else:
            return f"See: {instructions['linux']}"  # Default to Linux instructions

    def validate_tool(self, tool: str, tool_info: Dict) -> ValidationResult:
        """Validate that a required tool is installed and accessible"""
        try:
            result = subprocess.run(
                [tool, "--version"], capture_output=True, text=True, check=True
            )
            version = result.stdout.strip()
            impact = self.analyze_impact(tool, "version_change")
            return ValidationResult(
                True,
                f"✅ {tool} is installed",
                f"Version: {version}",
                impact_level=tool_info["impact_level"],
                requires_revalidation=impact.validation_required
            )
        except FileNotFoundError:
            return ValidationResult(
                False,
                f"❌ {tool} not found",
                f"Please install {tool_info['description']}\n"
                f"  {self.get_install_instructions(tool)}",
                impact_level=tool_info["impact_level"],
                requires_revalidation=True
            )
        except subprocess.CalledProcessError as e:
            return ValidationResult(
                False,
                f"❌ Error checking {tool}",
                f"Error: {e.stderr}",
                impact_level=tool_info["impact_level"],
                requires_revalidation=True
            )

    def validate_1password(self) -> ValidationResult:
        """Verify 1Password CLI is authenticated"""
        try:
            result = subprocess.run(
                ["op", "account", "list"],
                capture_output=True,
                text=True,
                check=True
            )
            if result.stdout.strip():
                return ValidationResult(
                    True,
                    "✅ 1Password CLI is authenticated"
                )
            return ValidationResult(
                False,
                "❌ No 1Password account found",
                "Please run: op signin"
            )
        except subprocess.CalledProcessError as e:
            return ValidationResult(
                False,
                "❌ 1Password CLI authentication failed",
                f"Error: {e.stderr}"
            )

    def validate_conda_env(self) -> ValidationResult:
        """Validate conda environment configuration"""
        env_file = self.workspace_root / "environment.yml"

        if not env_file.exists():
            return ValidationResult(
                False,
                "❌ environment.yml not found",
                "Please create environment.yml"
            )

        try:
            # Check if environment exists
            result = subprocess.run(
                ["conda", "env", "list", "--json"],
                capture_output=True,
                text=True,
                check=True,
            )
            envs = json.loads(result.stdout)

            # Get environment name from file
            with open(env_file) as f:
                env_config = yaml.safe_load(f)
                env_name = env_config.get("name", "chatbot-llm")

            if any(env_name in path for path in envs["envs"]):
                return ValidationResult(
                    True,
                    f"✅ Conda environment '{env_name}' exists"
                )
            else:
                return ValidationResult(
                    False,
                    f"❌ Conda environment '{env_name}' not found",
                    "Run: conda env create -f environment.yml"
                )

        except (subprocess.CalledProcessError, json.JSONDecodeError) as e:
            return ValidationResult(
                False,
                "❌ Error checking conda environment",
                f"Error: {str(e)}"
            )

    def validate_git_config(self) -> ValidationResult:
        """Validate git configuration"""
        try:
            # Check git config
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
                return ValidationResult(
                    True,
                    "✅ Git configuration is valid",
                    f"User: {name} <{email}>"
                )
            else:
                return ValidationResult(
                    False,
                    "❌ Incomplete git configuration",
                    "Please configure git user.name and user.email"
                )

        except subprocess.CalledProcessError as e:
            return ValidationResult(
                False,
                "❌ Error checking git configuration",
                f"Error: {e.stderr}"
            )

    def extract_ownership_info(self, file_path: Path) -> Optional[OwnershipInfo]:
        """Extract ownership information from file header comments"""
        if not file_path.exists():
            return None

        try:
            content = file_path.read_text()
            lines = content.split("\n")[:10]  # Check first 10 lines

            ownership_info = {}
            for line in lines:
                if line.startswith("#"):
                    if "Owned by:" in line:
                        ownership_info["ontology"] = line.split("Owned by:")[1].strip()
                    elif "Version:" in line:
                        ownership_info["version"] = line.split("Version:")[1].strip()
                    elif "Purpose:" in line:
                        ownership_info["purpose"] = line.split("Purpose:")[1].strip()

            if "ontology" in ownership_info:
                return OwnershipInfo(
                    ontology=ownership_info.get("ontology", "Unknown"),
                    version=ownership_info.get("version", "0.0.0"),
                    purpose=ownership_info.get(
                        "purpose", "No purpose specified"
                    ),
                )
        except Exception as e:
            self.logger.error(
                f"Error extracting ownership info from {file_path}: {e}"
            )

        return None

    def validate_ownership(self, file_path: Path) -> ValidationResult:
        """Validate ownership information in configuration files"""
        ownership_info = self.extract_ownership_info(file_path)

        if not ownership_info:
            return ValidationResult(
                False,
                f"❌ Missing ownership information in {file_path.name}",
                "File should specify Owned by:, Version:, and Purpose:",
            )

        return ValidationResult(
            True,
            f"✅ Valid ownership information in {file_path.name}",
            f"Owned by: {ownership_info.ontology}, "
            f"Version: {ownership_info.version}",
        )

    def validate_required_files(self) -> List[ValidationResult]:
        """Validate presence of required files and their ownership information"""
        results = []
        for filename, info in self.required_files.items():
            file_path = self.workspace_root / filename
            if file_path.exists():
                # Check for configuration drift
                has_drifted, drift_pct = self.detect_configuration_drift(
                    file_path, info["drift_threshold"]
                )
                
                if has_drifted:
                    results.append(
                        ValidationResult(
                            False,
                            f"⚠️ Configuration drift detected in {filename}",
                            f"Drift threshold exceeded: {drift_pct:.1%}",
                            impact_level=info["impact_level"],
                            requires_revalidation=True
                        )
                    )
                else:
                    results.append(
                        ValidationResult(
                            True,
                            f"✅ Found {filename}",
                            info["purpose"],
                            impact_level=info["impact_level"]
                        )
                    )

                # Check ownership for configuration files
                if filename.endswith((".yml", ".toml", ".template", ".example")):
                    ownership_result = self.validate_ownership(file_path)
                    results.append(ownership_result)
            else:
                results.append(
                    ValidationResult(
                        False,
                        f"❌ Missing {filename}",
                        f"Required for: {info['purpose']}",
                        impact_level=info["impact_level"],
                        requires_revalidation=True
                    )
                )
        return results

    def run_validation(self) -> bool:
        """Run all validation checks"""
        self.logger.info("Starting environment validation")
        all_valid = True
        revalidation_required = set()

        # 1. Check required tools
        self.logger.info("Checking required tools...")
        for tool, tool_info in self.required_tools.items():
            result = self.validate_tool(tool, tool_info)
            print(result.message)
            if result.details:
                print(f"  {result.details}")
            if not result.success:
                all_valid = False
                if result.requires_revalidation:
                    revalidation_required.add(tool)

        # 2. Check 1Password authentication
        self.logger.info("Checking 1Password authentication...")
        result = self.validate_1password()
        print(result.message)
        if result.details:
            print(f"  {result.details}")
        if not result.success:
            all_valid = False
            if result.requires_revalidation:
                revalidation_required.add("1password")

        # 3. Check conda environment
        self.logger.info("Checking conda environment...")
        result = self.validate_conda_env()
        print(result.message)
        if result.details:
            print(f"  {result.details}")
        if not result.success:
            all_valid = False
            if result.requires_revalidation:
                revalidation_required.add("conda")

        # 4. Check git configuration
        self.logger.info("Checking git configuration...")
        result = self.validate_git_config()
        print(result.message)
        if result.details:
            print(f"  {result.details}")
        if not result.success:
            all_valid = False
            if result.requires_revalidation:
                revalidation_required.add("git")

        # 5. Check required files
        self.logger.info("Checking required files...")
        for result in self.validate_required_files():
            print(result.message)
            if result.details:
                print(f"  {result.details}")
            if not result.success:
                all_valid = False

        if revalidation_required:
            revalidation_list = sorted(revalidation_required)
            self.logger.warning(
                "Revalidation required for: %s",
                ", ".join(revalidation_list)
            )

        return all_valid


def main():
    """Main entry point"""
    validator = LocalEnvValidator()
    success = validator.run_validation()

    if success:
        print("\n✅ Local environment validation successful!")
        sys.exit(0)
    else:
        print("\n❌ Local environment validation failed!")
        print("Please fix the reported issues and run validation again.")
        sys.exit(1)


if __name__ == "__main__":
    main()
