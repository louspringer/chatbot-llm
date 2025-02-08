#!/usr/bin/env python3

"""
Tool to maintain consistency between pyproject.toml and conda environment
configuration files.
"""

import tomli
import tomli_w
import yaml
import argparse
from pathlib import Path
from typing import Dict, Optional


class DependencyManager:
    def __init__(self, workspace_root: Path):
        self.workspace_root = workspace_root
        self.pyproject_path = workspace_root / "pyproject.toml"
        self.environment_path = workspace_root / "environment.yml"
        
    def read_pyproject(self) -> Dict:
        """Read pyproject.toml configuration."""
        if not self.pyproject_path.exists():
            raise FileNotFoundError(
                f"pyproject.toml not found at {self.pyproject_path}"
            )
        
        with open(self.pyproject_path, "rb") as f:
            return tomli.load(f)
    
    def read_environment(self) -> Dict:
        """Read environment.yml configuration."""
        if not self.environment_path.exists():
            return {
                "name": "chatbot-llm",
                "channels": ["conda-forge"],
                "dependencies": []
            }
        
        with open(self.environment_path) as f:
            return yaml.safe_load(f)
    
    def write_pyproject(self, config: Dict):
        """Write pyproject.toml configuration."""
        with open(self.pyproject_path, "wb") as f:
            tomli_w.dump(config, f)
    
    def write_environment(self, config: Dict):
        """Write environment.yml configuration."""
        with open(self.environment_path, "w") as f:
            yaml.safe_dump(config, f, sort_keys=False)
    
    def add_dependency(
        self,
        package: str,
        version: Optional[str] = None,
        dev: bool = False,
        conda_only: bool = False,
        pip_only: bool = False
    ):
        """Add a dependency to both pyproject.toml and environment.yml."""
        if conda_only and pip_only:
            raise ValueError("Cannot be both conda_only and pip_only")
        
        # Update pyproject.toml
        if not pip_only:
            pyproject = self.read_pyproject()
            dep_str = f"{package}{version if version else ''}"
            
            if dev:
                deps = (pyproject.get("project", {})
                       .get("optional-dependencies", {})
                       .get("dev", []))
                deps.append(dep_str)
                (pyproject.setdefault("project", {})
                 .setdefault("optional-dependencies", {})["dev"]) = sorted(set(deps))
            else:
                deps = pyproject.get("project", {}).get("dependencies", [])
                deps.append(dep_str)
                pyproject.setdefault("project", {})["dependencies"] = sorted(set(deps))
            
            self.write_pyproject(pyproject)
        
        # Update environment.yml
        if not conda_only:
            env = self.read_environment()
            dep_str = f"{package}{version if version else ''}"
            
            if pip_only:
                # Add to pip dependencies
                pip_deps = next(
                    (d["pip"] for d in env.get("dependencies", [])
                     if isinstance(d, dict) and "pip" in d),
                    None
                )
                if pip_deps is None:
                    env.setdefault("dependencies", []).append({"pip": [dep_str]})
                else:
                    pip_deps.append(dep_str)
            else:
                # Add to conda dependencies
                deps = [
                    d for d in env.get("dependencies", [])
                    if isinstance(d, str)
                ]
                deps.append(dep_str)
                env["dependencies"] = sorted(set(deps))
            
            self.write_environment(env)


def main():
    parser = argparse.ArgumentParser(description="Manage project dependencies")
    parser.add_argument("action", choices=["add"], help="Action to perform")
    parser.add_argument("package", help="Package name")
    parser.add_argument("--version", help="Package version constraint")
    parser.add_argument(
        "--dev",
        action="store_true",
        help="Add as development dependency"
    )
    parser.add_argument(
        "--conda-only",
        action="store_true",
        help="Only add to environment.yml"
    )
    parser.add_argument(
        "--pip-only",
        action="store_true",
        help="Only add to pip dependencies"
    )
    
    args = parser.parse_args()
    manager = DependencyManager(Path.cwd())
    
    if args.action == "add":
        manager.add_dependency(
            args.package,
            args.version,
            args.dev,
            args.conda_only,
            args.pip_only
        )


if __name__ == "__main__":
    main() 