#!/usr/bin/env python3
# Ontology: tools:SessionValidation
# Implements: tools:ValidationFramework
# Requirement: REQ-TOOLS-002 Session State Validation
# Guidance: guidance:TestingPattern#SessionValidation
# Description: Tool for validating session state and ensuring consistency

import argparse
import logging
import sys
from datetime import datetime, timezone
from pathlib import Path

from rdflib import Graph, Namespace
from rdflib.namespace import RDF

# Configure logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

# Constants
SESSION = Namespace("./session#")
GUIDANCE = Namespace("./guidance#")


def validate_session_state(
    session_file: Path,
    *,
    allow_absolute_paths: bool = False,
) -> bool:
    """Validate session.ttl state."""
    g = Graph()
    g.parse(session_file, format="turtle")

    errors = []

    # Check for current context
    current_context = g.value(None, RDF.type, SESSION.ContextState)
    if not current_context:
        errors.append("Missing current context state")

    # Check for active task
    if current_context:
        active_task = g.value(current_context, SESSION.activeTask, None)
        if not active_task:
            errors.append("Missing active task")

    # Check for active ontologies
    active_onts = list(g.objects(current_context, SESSION.activeOntologies))
    if not active_onts:
        errors.append("No active ontologies")

    # Check for security context
    sec_context = g.value(current_context, SESSION.securityContext, None)
    if not sec_context:
        errors.append("Missing security context")

    # Check timestamp
    last_update = g.value(current_context, SESSION.lastUpdated, None)
    if not last_update:
        errors.append("Missing last update timestamp")
    else:
        try:
            update_time = datetime.fromisoformat(
                str(last_update).replace("Z", "+00:00"),
            )
            days_old = (datetime.now(timezone.utc) - update_time).days
            if days_old > 7:
                logger.warning("Session state is %d days old", days_old)
        except ValueError as e:
            errors.append(f"Invalid timestamp format: {e}")

    if errors:
        for error in errors:
            logger.error(error)
        return False
    return True


def validate_session_log(
    log_file: Path,
    *,
    allow_absolute_paths: bool = False,
) -> bool:
    """Validate session_log.ttl state."""
    g = Graph()
    g.parse(log_file, format="turtle")

    errors = []

    # Check for at least one log entry
    entries = list(g.subjects(RDF.type, GUIDANCE.SessionLogEntry))
    if not entries:
        errors.append("No session log entries found")

    # Validate each entry
    for entry in entries:
        # Check required properties
        if not g.value(entry, GUIDANCE.hasActor, None):
            errors.append(f"Missing actor for entry {entry}")
        if not g.value(entry, GUIDANCE.hasTimestamp, None):
            errors.append(f"Missing timestamp for entry {entry}")
        if not g.value(entry, GUIDANCE.hasChangeReason, None):
            errors.append(f"Missing change reason for entry {entry}")

    if errors:
        for error in errors:
            logger.error(error)
        return False
    return True


def main():
    """Main validation function."""
    parser = argparse.ArgumentParser(description="Validate session state files")
    parser.add_argument(
        "--allow-absolute-paths",
        action="store_true",
        help="Allow absolute paths in session files",
    )
    args = parser.parse_args()

    session_file = Path("session.ttl")
    log_file = Path("session_log.ttl")

    # Check if files exist
    if not session_file.exists():
        logger.error("Session file not found: %s", session_file)
        return False
    if not log_file.exists():
        logger.error("Session log file not found: %s", log_file)
        return False

    # Run validations
    session_valid = validate_session_state(
        session_file,
        allow_absolute_paths=args.allow_absolute_paths,
    )
    log_valid = validate_session_log(
        log_file,
        allow_absolute_paths=args.allow_absolute_paths,
    )

    if not session_valid or not log_valid:
        return False

    logger.info("Session state validation passed")
    return True


if __name__ == "__main__":
    success = main()
    sys.exit(0 if success else 1)
