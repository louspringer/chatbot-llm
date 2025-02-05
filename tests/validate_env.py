#!/usr/bin/env python3
"""
Environment validation script for the Snowflake Cortex Teams Bot project.
Validates all required dependencies and environment setup.
"""

import sys
import os
from typing import Dict, List, Tuple
import importlib
import pkg_resources
import platform


def check_python_version() -> Tuple[bool, str]:
    """Validate Python version meets requirements."""
    version = sys.version_info
    if version.major == 3 and 10 <= version.minor < 12:
        return True, f"Python version {sys.version} OK"
    return False, f"Python version {sys.version} not in range >=3.10,<3.12"


def check_package(package: str, min_version: str) -> Tuple[bool, str]:
    """Check if a package is installed and meets minimum version."""
    try:
        if package.startswith('botbuilder.'):
            # For botbuilder packages, just check the distribution
            # Package name: botbuilder.core -> botbuilder-core
            # Special case for integration packages:
            # botbuilder.integration.aiohttp -> botbuilder-integration-aiohttp
            module_path = package.split('.')
            if module_path[1] == 'integration':
                dist_name = (
                    f"{module_path[0]}-{module_path[1]}-{module_path[2]}"
                )
            else:
                dist_name = f"{module_path[0]}-{module_path[1]}"
            version = pkg_resources.get_distribution(dist_name).version
        elif package == "snowflake-snowpark-python":
            # For snowpark, we check the actual module
            importlib.import_module("snowflake.snowpark")
            version = pkg_resources.get_distribution(package).version
        else:
            # Handle regular packages
            module_name = package.replace("-", "_")
            importlib.import_module(module_name)
            version = pkg_resources.get_distribution(package).version
        
        parsed_version = pkg_resources.parse_version(version)
        parsed_min = pkg_resources.parse_version(min_version)
        
        if parsed_version >= parsed_min:
            return True, f"{package} version {version} OK"
        return False, f"{package} version {version} < required {min_version}"
    except ImportError:
        return False, f"{package} not installed"
    except Exception as e:
        return False, f"Error checking {package}: {str(e)}"


def check_core_dependencies() -> List[Tuple[bool, str]]:
    """Check core project dependencies."""
    return [
        check_package("rdflib", "6.0.0"),
        check_package("owlready2", "0.37"),
        check_package("pyshacl", "0.20.0"),
    ]


def check_teams_bot_dependencies() -> List[Tuple[bool, str]]:
    """Check Teams Bot specific dependencies."""
    return [
        check_package("botbuilder.core", "4.14.0"),
        check_package("botbuilder.schema", "4.14.0"),
        check_package("botbuilder.dialogs", "4.14.0"),
        check_package("botbuilder.ai", "4.14.0"),
        check_package("botbuilder.integration.aiohttp", "4.14.0"),
    ]


def check_snowflake_dependencies() -> List[Tuple[bool, str]]:
    """Check Snowflake integration dependencies."""
    results = []
    
    # Check package installation
    results.extend([
        check_package("snowflake-snowpark-python", "1.0.0"),
    ])
    
    # Validate Snowpark session
    try:
        from snowflake.snowpark import Session
        
        # Create session with minimal config
        session = Session.builder.configs({}).create()
        
        # Run test query
        result = session.sql(
            "SELECT CURRENT_WAREHOUSE() as warehouse"
        ).collect()
        if result and result[0]['WAREHOUSE']:
            warehouse = result[0]['WAREHOUSE']
            results.append((True, f"Connected to warehouse: {warehouse}"))
        else:
            results.append((False, "Snowpark session query failed"))
        session.close()
    except Exception as e:
        err_msg = f"Snowpark session validation failed: {str(e)}"
        results.append((False, err_msg))
    
    return results


def check_dev_tools() -> List[Tuple[bool, str]]:
    """Check development tool dependencies."""
    return [
        check_package("pytest", "7.0.0"),
        check_package("pytest-cov", "3.0.0"),
        check_package("black", "24.0.0"),
        check_package("flake8", "7.0.0"),
        check_package("mypy", "1.8.0"),
    ]


def check_environment_variables() -> List[Tuple[bool, str]]:
    """Check required environment variables."""
    required_vars = [
        "PYTHONPATH",
        "AZURE_FUNCTIONS_ENVIRONMENT",
    ]
    results = []
    for var in required_vars:
        if var in os.environ:
            results.append((True, f"Environment variable {var} is set"))
        else:
            results.append((False, f"Environment variable {var} is not set"))
    return results


def main():
    """Main validation function."""
    all_checks: Dict[str, List[Tuple[bool, str]]] = {
        "Python Version": [check_python_version()],
        "Core Dependencies": check_core_dependencies(),
        "Teams Bot Dependencies": check_teams_bot_dependencies(),
        "Snowflake Dependencies": check_snowflake_dependencies(),
        "Development Tools": check_dev_tools(),
        "Environment Variables": check_environment_variables(),
    }

    print("\nEnvironment Validation Results:")
    print("=" * 50)

    all_passed = True
    for category, checks in all_checks.items():
        print(f"\n{category}:")
        for passed, message in checks:
            status = "✓" if passed else "✗"
            print(f"{status} {message}")
            if not passed:
                all_passed = False

    print("\nSystem Information:")
    print(f"Platform: {platform.platform()}")
    print(f"Python: {sys.version}")
    print(f"Executable: {sys.executable}")

    if not all_passed:
        print("\n❌ Some checks failed. Please review the output above.")
        sys.exit(1)
    else:
        print("\n✅ All validation checks passed!")


if __name__ == "__main__":
    main()