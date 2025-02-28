"""
# Ontology: session:SessionContextManager
# Implements: session:StateManagement
# Requirement: REQ-SES-001 Session State Management
# Guidance: guidance:ModelFirstPrinciple#stateManagement
# Description: Manages session context operations using LLM assistance
"""

import argparse
import json
import logging
import os
import sys
import warnings
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from rich.console import Console

try:
    from anthropic import Client
except ImportError:
    msg = "anthropic package is required. Install with: conda install anthropic"
    raise ImportError(msg)

from rdflib import Graph, Literal, Namespace, URIRef
from rdflib.namespace import RDF, RDFS, XSD
from rich.syntax import Syntax

# Configure logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

# Constants - use relative paths
SESSION_FILE = Path("session.ttl")
SESSION_LOG_FILE = Path("session_log.ttl")

# Namespaces - use relative paths for local ontologies
SESSION = Namespace("./session#")
SESSION_LOG = Namespace("./session_log#")
GUIDANCE = Namespace("./guidance#")
LOG = Namespace("./session_log#")

# Suppress deprecation warnings
warnings.filterwarnings("ignore", category=DeprecationWarning)


def ensure_relative_uri(uri: str) -> str:
    """Convert absolute file URIs to relative ones."""
    if uri.startswith("file:///"):
        # Extract the path part and make it relative
        path = uri.split("file:///")[-1]
        return f'./{path.split("/")[-1]}'
    return uri


def is_valid_uri(s: str) -> bool:
    """Check if a string is a valid URI."""
    invalid_chars = '<>"{}|\\^`'
    return not any(c in s for c in invalid_chars)


class SessionContextManager:
    def __init__(self, dry_run: bool = False) -> None:
        # Check API key first
        api_key_error = "ANTHROPIC_API_KEY environment variable not set"
        if not os.getenv("ANTHROPIC_API_KEY"):
            raise ValueError(api_key_error)

        self.client = Client()
        self.dry_run = dry_run
        self.token_usage = []

        # Initialize graphs
        self.session_graph = Graph()
        self.log_graph = Graph()

        # Bind namespaces
        for g in [self.session_graph, self.log_graph]:
            g.bind("", SESSION)
            g.bind("guidance", GUIDANCE)
            g.bind("log", LOG)

        if not self.dry_run:
            self.load_graphs()

    def load_graphs(self) -> None:
        """Load session and log graphs from files."""
        # Check if files exist
        session_file_error = f"Session file not found: {SESSION_FILE}"
        log_file_error = f"Session log file not found: {SESSION_LOG_FILE}"

        if not Path(SESSION_FILE).exists():
            raise FileNotFoundError(session_file_error)
        if not Path(SESSION_LOG_FILE).exists():
            raise FileNotFoundError(log_file_error)

        # Load graphs
        self.session_graph.parse(SESSION_FILE, format="turtle")
        self.log_graph.parse(SESSION_LOG_FILE, format="turtle")

    def save_graphs(self):
        """Save session and log graphs to files."""
        # Get all triples from both graphs
        session_triples = list(self.session_graph)
        log_triples = list(self.log_graph)

        # Clear graphs before re-adding with correct types
        self.session_graph.remove((None, None, None))
        self.log_graph.remove((None, None, None))

        # Re-add triples with correct types
        for s, p, o in session_triples:
            if isinstance(o, Literal):
                # Keep existing literals as is
                self.session_graph.add((s, p, o))
            elif isinstance(o, str):
                # Check if this is a label, comment, or change reason
                pred_str = str(p)
                semantic_predicates = {"label", "comment", "changeReason"}
                if any(x in pred_str for x in semantic_predicates):
                    # Labels, comments, and change reasons should be literals
                    self.session_graph.add(
                        (s, p, Literal(o, datatype=XSD.string)),
                    )
                elif is_valid_uri(o):
                    if o.startswith("file:///"):
                        relative_uri = URIRef(ensure_relative_uri(o))
                        self.session_graph.add((s, p, relative_uri))
                    else:
                        self.session_graph.add((s, p, URIRef(o)))
                else:
                    # Use Literal for non-URI strings
                    self.session_graph.add(
                        (s, p, Literal(o, datatype=XSD.string)),
                    )
            else:
                self.session_graph.add((s, p, o))

        for s, p, o in log_triples:
            if isinstance(o, Literal):
                # Keep existing literals as is
                self.log_graph.add((s, p, o))
            elif isinstance(o, str):
                # Check if this is a label, comment, or change reason
                pred_str = str(p)
                semantic_predicates = {"label", "comment", "changeReason"}
                if any(x in pred_str for x in semantic_predicates):
                    # Labels, comments, and change reasons should be literals
                    self.log_graph.add((s, p, Literal(o, datatype=XSD.string)))
                elif is_valid_uri(o):
                    if o.startswith("file:///"):
                        relative_uri = URIRef(ensure_relative_uri(o))
                        self.log_graph.add((s, p, relative_uri))
                    else:
                        self.log_graph.add((s, p, URIRef(o)))
                else:
                    # Use Literal for non-URI strings
                    self.log_graph.add((s, p, Literal(o, datatype=XSD.string)))
            else:
                self.log_graph.add((s, p, o))

        # Save to files
        if not self.dry_run:
            self.session_graph.serialize(SESSION_FILE, format="turtle")
            self.log_graph.serialize(SESSION_LOG_FILE, format="turtle")

    def _track_usage(self, response: Any, operation: str) -> None:
        """Track token usage from Claude response"""
        try:
            usage = {
                "operation": operation,
                "timestamp": datetime.now(tz=timezone.utc).isoformat(),
                "input_tokens": response.usage.input_tokens,
                "output_tokens": response.usage.output_tokens,
                "total_tokens": response.usage.input_tokens
                + response.usage.output_tokens,
            }
            self.token_usage.append(usage)

            if os.getenv("DEBUG"):
                print("\nToken Usage:")
                print(f'Operation:     {usage["operation"]}')
                print(f'Input tokens:  {usage["input_tokens"]}')
                print(f'Output tokens: {usage["output_tokens"]}')
                print(f'Total tokens:  {usage["total_tokens"]}')
        except Exception as e:  # noqa: BLE001
            msg = f"Warning: Failed to track token usage: {str(e)}"  # noqa
            print(msg)

    def get_token_usage(self) -> dict:
        """Get token usage statistics"""
        if not self.token_usage:
            if self.dry_run:
                print("\n=== Token Usage Summary ===")
                print("No token usage recorded yet")
            return {
                "operations": 0,
                "total_tokens": 0,
                "average_tokens": 0,
                "details": [],
            }

        total_tokens = sum(u["total_tokens"] for u in self.token_usage)
        operations = len(self.token_usage)

        summary = {
            "operations": operations,
            "total_tokens": total_tokens,
            "average_tokens": (total_tokens / operations if operations > 0 else 0),
            "details": self.token_usage,
        }

        if self.dry_run:
            print("\n=== Token Usage Summary ===")
            print(f"Total operations: {operations}")
            print(f"Total tokens:     {total_tokens}")
            print(f'Average tokens:   {summary["average_tokens"]:.2f}')
            print("\nOperation Details:")
            for usage in self.token_usage:
                msg = f'- {usage["operation"]}: {usage["total_tokens"]}'
                print(f"{msg} tokens")

        return summary

    def create_context(
        self,
        task_id: str,
        ontologies: list[str],
        description: str,
        security_level: str = "High",
        requires_validation: bool = True,
    ) -> str:
        """Create a new context with specified parameters"""
        # Format context data for prompt
        context_prompt = (
            f"Create a new context with:\n"
            f"Task ID: {task_id}\n"
            f'Ontologies: {", ".join(ontologies)}\n'
            f"Description: {description}\n"
            f"Security Level: {security_level}\n"
            f"Requires Validation: {requires_validation}"
        )

        # type: ignore[call-arg]
        response = self.client.messages.create(
            model="claude-3-sonnet-20240229",
            max_tokens=1000,
            temperature=0,
            system=(
                "You are a semantic web expert. Generate "
                "Turtle RDF for creating a new context."
            ),
            messages=[{"role": "user", "content": context_prompt}],
        )

        self._track_usage(response, "create_context")

        # Extract text from response content and update session
        content_text = (
            "\n".join(str(block) for block in response.content)
            if response.content
            else ""
        )
        self.update_session_and_log(content_text, content_text)

        return self.get_current_context()

    def detect_context_mismatch(self) -> str | None:
        """Detect if current context might be invalid based on heuristics"""
        if self.dry_run:
            print("\n=== Context Mismatch Detection (Dry Run) ===")

        mismatches = []

        try:
            # Check if active task exists
            task = self.session_graph.value(None, SESSION.activeTask, None)
            if task:
                if not any(
                    self.session_graph.triples((task, RDF.type, SESSION.Task)),
                ):
                    mismatches.append("Active task reference is invalid")
                if self.dry_run:
                    print(f"Active Task Check: {task}")

            # Check if ontologies exist and are properly linked
            onts = list(
                self.session_graph.objects(None, SESSION.activeOntologies),
            )
            if onts:
                invalid_onts = [ont for ont in onts if ":" not in str(ont)]
                if invalid_onts:
                    msg = f"Invalid ontology refs: {invalid_onts}"
                    mismatches.append(msg)
                if self.dry_run:
                    print(f"Active Ontologies: {onts}")

            # Check timestamp freshness
            last_update = self.session_graph.value(
                None,
                SESSION.lastUpdated,
                None,
            )
            if last_update:
                update_time = datetime.fromisoformat(
                    str(last_update).replace("Z", "+00:00"),
                )
                days_old = (datetime.now() - update_time).days
                if days_old > 7:
                    mismatches.append(f"Context is {days_old} days old")
                if self.dry_run:
                    print(f"Last Update: {last_update} ({days_old} days old)")

            # Check security context
            sec_context = self.session_graph.value(
                None,
                SESSION.securityContext,
                None,
            )
            if not sec_context:
                mismatches.append("Missing security context")

            # Check cursor rules
            rules = list(self.session_graph.objects(None, SESSION.cursorRules))
            if rules:
                invalid_rules = [
                    rule
                    for rule in rules
                    if not any(
                        self.session_graph.triples(
                            (rule, RDF.type, SESSION.CursorRule),
                        ),
                    )
                ]
                if invalid_rules:
                    mismatches.append(f"Invalid rules: {invalid_rules}")

            # Check for orphaned nodes
            for current_context in self.session_graph.subjects(
                RDF.type,
                SESSION.ContextState,
            ):
                for pred, obj in self.session_graph.predicate_objects(
                    current_context,
                ):
                    if not any(self.session_graph.triples((obj, None, None))):
                        mismatches.append(f"Orphaned: {obj}")

            return "\n".join(mismatches) if mismatches else None

        except Exception as e:
            msg = f"Error in context check: {str(e)}"  # noqa
            return msg

    def get_current_context(self) -> str:
        """Get the current context."""
        if self.dry_run:
            return """
@prefix : <./session#> .
@prefix session: <./session#> .
@prefix rdf: <http://www.w3.org/1999/02/22-rdf-syntax-ns#> .

:test_context a session:Context ;
    session:isActive true .
"""

        try:
            # Query for current context
            query = """
                SELECT ?context
                WHERE {
                    ?context a :Context ;
                            :isActive true .
                }
                LIMIT 1
            """
            results = self.session_graph.query(query)
            for result in results:
                if result and isinstance(result, (list, tuple)) and len(result) > 0:
                    return str(result[0])
            return ""
        except Exception as e:
            logger.error("Error getting current context: %s", e)
            return ""

    def list_contexts(self) -> dict:
        """List all contexts in the session log with their identifiers"""
        # Query the graph for all entries
        entries = []
        for entry in self.log_graph.subjects(RDF.type, None):
            entry_id = str(entry).split("#")[-1]
            if not entry_id.startswith(
                "http",
            ):  # Skip entries with full URIs
                entry_data = {
                    "id": entry_id,
                    "timestamp": str(
                        self.log_graph.value(entry, GUIDANCE.hasTimestamp) or "",
                    ),
                    "actor": str(
                        self.log_graph.value(entry, GUIDANCE.hasActor) or "",
                    ),
                    "reason": str(
                        self.log_graph.value(entry, GUIDANCE.hasChangeReason) or "",
                    ),
                    "state": {},
                }

                # Get state information
                for pred, obj in self.log_graph.predicate_objects(entry):
                    pred_str = str(pred).split("#")[-1]
                    if pred_str in [
                        "activeCursorRules",
                        "activeOntologies",
                        "configurationFiles",
                    ]:
                        # Handle list values
                        values = [
                            str(o).split("#")[-1]
                            for o in self.log_graph.objects(entry, pred)
                        ]
                        entry_data["state"][pred_str] = values
                    elif pred_str in [
                        "hasWorkingConfig",
                        "requiresValidation",
                    ]:
                        # Handle boolean values
                        entry_data["state"][pred_str] = str(obj).lower() == "true"
                    elif pred_str not in [
                        "type",
                        "hasTimestamp",
                        "hasActor",
                        "hasChangeReason",
                    ]:
                        # Handle other values
                        value = str(obj)
                        if "#" in value:
                            value = value.split("#")[-1]
                        entry_data["state"][pred_str] = value

                entries.append(entry_data)

        # Sort entries by timestamp
        entries.sort(key=lambda x: x["timestamp"])

        # Get current context state
        current_state = {}
        if current_context := self.session_graph.value(
            None,
            RDF.type,
            SESSION.ContextState,
        ):
            for pred, obj in self.session_graph.predicate_objects(
                current_context,
            ):
                pred_str = str(pred).split("#")[-1]
                if pred_str in [
                    "activeCursorRules",
                    "activeOntologies",
                    "configurationFiles",
                ]:
                    # Handle list values
                    values = [
                        str(o).split("#")[-1]
                        for o in self.session_graph.objects(
                            current_context,
                            pred,
                        )
                    ]
                    current_state[pred_str] = values
                elif pred_str in ["hasWorkingConfig", "requiresValidation"]:
                    # Handle boolean values
                    current_state[pred_str] = str(obj).lower() == "true"
                elif pred_str not in ["type"]:
                    # Handle other values
                    value = str(obj)
                    if "#" in value:
                        value = value.split("#")[-1]
                    current_state[pred_str] = value

        return {"contexts": entries, "current_state": current_state}

    def pop_context(self) -> str:
        """Pop the current context."""
        if self.dry_run:
            return """
@prefix : <./session#> .
@prefix session: <./session#> .
@prefix rdf: <http://www.w3.org/1999/02/22-rdf-syntax-ns#> .

:test_context a session:Context ;
    session:isActive false .
"""

        try:
            # Get current context
            current = self.get_current_context()
            if not current:
                return ""

            # Remove active flag
            self.session_graph.remove(
                (URIRef(current), SESSION.isActive, Literal(True)),
            )
            if not self.dry_run:
                self.save_graphs()

            return current
        except Exception as e:
            logger.error("Error popping context: %s", e)
            return ""

    def search_contexts(self, query: str) -> str:
        """Search for contexts matching the query."""
        if self.dry_run:
            return """
@prefix : <./session#> .
@prefix session: <./session#> .
@prefix rdf: <http://www.w3.org/1999/02/22-rdf-syntax-ns#> .

:test_context a session:Context ;
    session:matchesQuery true .
"""

        try:
            # Call Claude for assistance
            response = self.client.messages.create(
                model="claude-3-sonnet-20240229",
                max_tokens=1000,
                temperature=0,
                messages=[
                    {
                        "role": "user",
                        "content": (
                            f"Search for contexts matching: {query}\n"
                            "Return results in Turtle format."
                        ),
                    },
                ],
            )

            self._track_usage(response, "search_contexts")
            return str(response.content)
        except Exception as e:
            logger.error("Error searching contexts: %s", e)
            return ""

    def restore_context(self, context_id: str) -> str:
        """Restore a previous context."""
        if self.dry_run:
            return """
@prefix : <./session#> .
@prefix session: <./session#> .
@prefix rdf: <http://www.w3.org/1999/02/22-rdf-syntax-ns#> .

:test_context a session:Context ;
    session:isRestored true .
"""

        try:
            # Call Claude for assistance
            response = self.client.messages.create(
                model="claude-3-sonnet-20240229",
                max_tokens=1000,
                temperature=0,
                messages=[
                    {
                        "role": "user",
                        "content": (
                            f"Restore context with ID: {context_id}\n"
                            "Return context in Turtle format."
                        ),
                    },
                ],
            )

            self._track_usage(response, "restore_context")

            # Update session graph with restored context
            restored_graph = Graph()
            restored_graph.parse(data=str(response.content), format="turtle")

            # Add restored triples to session graph
            for triple in restored_graph:
                self.session_graph.add(triple)

            if not self.dry_run:
                self.save_graphs()

            return str(response.content)
        except Exception as e:
            logger.error("Error restoring context: %s", e)
            return ""

    def _extract_text(self, response: Any) -> str:
        """Extract text content from a Claude response"""
        # First get the raw text
        if isinstance(response, list):
            text = str(response[0].text)
        elif hasattr(response, "text"):
            text = str(response.text)
        elif hasattr(response, "content"):
            content = response.content
            is_list = isinstance(content, list)
            text = str(content[0].text) if is_list else str(content)
        else:
            text = str(response)

        # Clean up markdown formatting
        if "```turtle" in text:
            # Extract content between turtle code blocks
            start = text.find("```turtle") + 8
            end = text.find("```", start)
            if end > start:
                text = text[start:end].strip()

        return text

    def update_session_and_log(
        self,
        log_update: str | None,
        session_update: str | None,
    ) -> None:
        """Update session and log files with new data."""
        # Parse log updates
        if log_update:
            log_update = self._extract_text(log_update)
            log_graph = Graph()
            log_graph.parse(data=log_update, format="turtle")
            self.log_graph += log_graph

        # Parse session updates
        if session_update:
            session_update = self._extract_text(session_update)
            session_graph = Graph()
            session_graph.parse(data=session_update, format="turtle")
            self.session_graph += session_graph

        # Create log entry only if there were updates
        if log_update or session_update:
            timestamp = datetime.now().strftime("%Y_%m_%d_%H%M%S")
            log_entry = URIRef(f"./session_log#entry_{timestamp}")

            # Add basic entry metadata
            self.log_graph.add((log_entry, RDF.type, GUIDANCE.SessionLogEntry))
            self.log_graph.add(
                (
                    log_entry,
                    RDFS.label,
                    Literal("Session Update", datatype=XSD.string),
                ),
            )
            self.log_graph.add((log_entry, GUIDANCE.hasActor, LOG.ClaudeAI))

            # Add timestamp
            self.log_graph.add(
                (
                    log_entry,
                    GUIDANCE.hasTimestamp,
                    Literal(datetime.now().isoformat(), datatype=XSD.dateTime),
                ),
            )

            # Add change reason
            self.log_graph.add(
                (
                    log_entry,
                    GUIDANCE.hasChangeReason,
                    Literal("Initial state", datatype=XSD.string),
                ),
            )

            # Save updated graphs
            self.save_graphs()

    def format_context_json(self, context_data: Any) -> dict:
        """Convert context data to JSON format"""
        # Handle TextBlock objects
        if hasattr(context_data, "text"):
            context_data = context_data.text
        elif isinstance(context_data, list) and hasattr(
            context_data[0],
            "text",
        ):
            context_data = context_data[0].text

        # Parse the text response into structured data
        if isinstance(context_data, str):
            lines = context_data.split("\n")
        else:
            lines = str(context_data).split("\n")

        result: dict = {"contexts": [], "current_state": {}}  # Add type hint
        current_dict: dict | None = None  # Add type hint
        in_state_summary = False

        for line in lines:
            line = line.strip()
            if not line:
                continue

            # Handle context entries
            if line.startswith("Entry ID:"):
                if current_dict:
                    result["contexts"].append(current_dict)
                current_dict = {"id": line.split(":", 1)[1].strip()}
            elif current_dict and line.startswith("Timestamp:"):
                current_dict["timestamp"] = line.split(":", 1)[1].strip()
            elif current_dict and line.startswith("Actor:"):
                current_dict["actor"] = line.split(":", 1)[1].strip()
            elif current_dict and line.startswith("Change Reason:"):
                current_dict["reason"] = line.split(":", 1)[1].strip()
            elif line.startswith("State summary:"):
                in_state_summary = True
                if current_dict:
                    current_dict["state"] = {}
            elif in_state_summary and line.startswith("- "):
                key, value = line[2:].split(":", 1)
                key = key.strip().lower().replace(" ", "_")
                value = value.strip()

                # Convert lists
                if "," in value:
                    value = [v.strip() for v in value.split(",")]
                # Convert booleans
                elif value.lower() in ["true", "false"]:
                    value = value.lower() == "true"

                if current_dict:
                    current_dict["state"][key] = value
                else:
                    result["current_state"][key] = value

        # Add the last context if any
        if current_dict:
            result["contexts"].append(current_dict)

        return result

    def format_output(
        self,
        data: dict,
        pretty: bool = False,
        color: bool = True,
    ) -> None:
        """Format and print output with optional colors and pretty printing"""
        console = Console(force_terminal=color)

        if pretty:
            # Pretty print with syntax highlighting
            json_str = json.dumps(data, indent=2)
            syntax = Syntax(json_str, "json", theme="monokai")
            console.print(syntax)
        else:
            # Compact JSON without colors
            print(json.dumps(data))


def main():
    """CLI interface for session context management"""
    parser = argparse.ArgumentParser(description="Session Context Manager")
    parser.add_argument("command", choices=["list", "pop", "search", "restore"])
    parser.add_argument(
        "param",
        nargs="?",
        help="Parameter for search/restore commands",
    )
    parser.add_argument(
        "-p",
        "--pretty",
        action="store_true",
        help="Pretty print output",
    )
    parser.add_argument(
        "--no-color",
        action="store_true",
        help="Disable colored output",
    )
    parser.add_argument(
        "--dry-run",
        action="store_true",
        help="Show changes without applying them",
    )
    args = parser.parse_args()

    manager = SessionContextManager(dry_run=args.dry_run)

    try:
        if args.command == "list":
            result = manager.list_contexts()
        elif args.command == "pop":
            result = manager.pop_context()
            result = manager.format_context_json(result)
        elif args.command == "search" and args.param:
            result = manager.search_contexts(args.param)
            result = manager.format_context_json(result)
        elif args.command == "restore" and args.param:
            result = manager.restore_context(args.param)
            result = manager.format_context_json(result)
        else:
            print("Invalid command or missing parameter")
            return

        manager.format_output(
            result,
            pretty=args.pretty,
            color=not args.no_color,
        )

    except Exception as e:
        print(f"Error: {e!s}")
        sys.exit(1)


if __name__ == "__main__":
    main()
