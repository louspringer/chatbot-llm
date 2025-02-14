#!/usr/bin/env python3
# type: ignore
"""
Session Context Manager - Manages session.ttl and session_log.ttl context
operations using LLM assistance for complex operations and maintaining semantic
consistency.
"""

import os
import sys
from datetime import datetime
from pathlib import Path
from typing import Any, Dict, List, Optional

try:
    import anthropic
except ImportError:
    msg = "anthropic package is required. Install it with: conda install anthropic"  # noqa: E501
    raise ImportError(msg)

import argparse
import json
import warnings

from rdflib import Graph, Namespace
from rdflib.namespace import RDF
from rich.console import Console
from rich.syntax import Syntax

# Constants
PROJECT_ROOT = Path(__file__).parent.parent.parent
SESSION_FILE = PROJECT_ROOT / "session.ttl"
SESSION_LOG_FILE = PROJECT_ROOT / "session_log.ttl"

# Namespaces
SESSION = Namespace("./session#")
SESSION_LOG = Namespace("./session_log#")
GUIDANCE = Namespace("./guidance#")

# Suppress deprecation warnings
warnings.filterwarnings("ignore", category=DeprecationWarning)


class SessionContextManager:
    def __init__(self, dry_run: bool = False):
        # Check API key first
        self.api_key = os.getenv("ANTHROPIC_API_KEY")
        if not self.api_key:
            raise ValueError(
                "ANTHROPIC_API_KEY environment variable not set"
            )  # noqa: E501

        self.client = anthropic.Client(api_key=self.api_key)
        self.session_graph = Graph()
        self.log_graph = Graph()
        self.dry_run = dry_run
        self.token_usage = []  # Track token usage
        self.load_graphs()

    def load_graphs(self):
        """Load both session.ttl and session_log.ttl graphs"""
        self.session_graph.parse(SESSION_FILE, format="turtle")
        self.log_graph.parse(SESSION_LOG_FILE, format="turtle")

    def save_graphs(self):
        """Save both graphs back to their files"""
        if self.dry_run:
            print("\n=== Dry Run: Changes to be made ===")
            print("\nsession.ttl changes:")
            print(self.session_graph.serialize(format="turtle"))
            print("\nsession_log.ttl changes:")
            print(self.log_graph.serialize(format="turtle"))
            return

        self.session_graph.serialize(SESSION_FILE, format="turtle")
        self.log_graph.serialize(SESSION_LOG_FILE, format="turtle")

    def _track_usage(self, response, operation: str):
        """Track token usage from Claude response"""
        try:
            usage = {
                "operation": operation,
                "timestamp": datetime.utcnow().isoformat(),
                "input_tokens": response.usage.input_tokens,
                "output_tokens": response.usage.output_tokens,
                "total_tokens": (
                    response.usage.input_tokens + response.usage.output_tokens
                ),
            }
            self.token_usage.append(usage)

            if self.dry_run:
                print(f"\n=== Token Usage for {operation} ===")
                print(f"Input tokens:  {usage['input_tokens']}")
                print(f"Output tokens: {usage['output_tokens']}")
                print(f"Total tokens:  {usage['total_tokens']}")
        except Exception as e:
            msg = f"Warning: Failed to track token usage for {operation}: {str(e)}"  # noqa: E501
            print(msg)

    def get_token_usage(self) -> Dict[str, Any]:
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
            print(f"Average tokens:   {summary['average_tokens']:.2f}")
            print("\nOperation Details:")
            for usage in self.token_usage:
                print(f"- {usage['operation']}: {usage['total_tokens']} tokens")

        return summary

    def create_context(
        self,
        task_id: str,
        ontologies: List[str],
        description: str,
        security_level: str = "High",
        requires_validation: bool = True,
    ) -> Dict[str, Any]:
        """
        Create a new context with specified parameters.

        Args:
            task_id: Identifier for the task
            ontologies: List of ontology names to activate
            description: Description of the context
            security_level: Security level (Low, Medium, High)
            requires_validation: Whether security validation is required

        Returns:
            Dict containing the created context details
        """
        if self.dry_run:
            print("\n=== Dry Run: Creating New Context ===")
            print(f"Task ID: {task_id}")
            print(f"Ontologies: {ontologies}")
            print(f"Description: {description}")
            print(f"Security Level: {security_level}")
            print(f"Requires Validation: {requires_validation}")
            return {"dry_run": True, "task_id": task_id}

        # Create context prompt
        context_prompt = f"""
        Given the following parameters for a new context:
        Task ID: {task_id}
        Ontologies: {ontologies}
        Description: {description}
        Security Level: {security_level}
        Requires Validation: {requires_validation}

        Generate Turtle RDF to create a new context in session.ttl with:
        1. Appropriate task and context nodes
        2. Active ontologies list
        3. Security context
        4. Timestamp and metadata

        Also generate a log entry for session_log.ttl.
        """

        response = self.client.messages.create(
            model="claude-3-sonnet-20240229",
            temperature=0,
            system=(
                "You are a semantic web expert. Generate Turtle RDF for creating a new "
                "context."
            ),
            messages=[{"role": "user", "content": context_prompt}],
        )

        self._track_usage(response, "create_context")

        # Update both files
        self.update_session_and_log(response.content, response.content)

        return self.get_current_context()

    def detect_context_mismatch(self) -> Optional[str]:
        """
        Detect if current context might be invalid based on heuristics.
        Returns reason for mismatch if detected, None otherwise.
        """
        if self.dry_run:
            print("\n=== Context Mismatch Detection (Dry Run) ===")

        mismatches = []

        try:
            # Check if active task exists
            task = self.session_graph.value(None, SESSION.activeTask, None)
            if task:
                task_type = (task, RDF.type, SESSION.Task)
                if not any(self.session_graph.triples(task_type)):  # noqa: E501
                    mismatches.append("Active task reference is invalid")
                if self.dry_run:
                    print(f"Active Task Check: {task}")

            # Check if ontologies exist and are properly linked
            onts = list(self.session_graph.objects(None, SESSION.activeOntologies))
            if onts:
                invalid_onts = [ont for ont in onts if ":" not in str(ont)]
                if invalid_onts:
                    msg = f"Invalid ontology references: {invalid_onts}"  # noqa: E501
                    mismatches.append(msg)
                if self.dry_run:
                    print(f"Active Ontologies: {onts}")

            # Check timestamp freshness
            last_update = self.session_graph.value(None, SESSION.lastUpdated, None)
            if last_update:
                update_time = datetime.fromisoformat(
                    str(last_update).replace("Z", "+00:00")
                )
                days_old = (datetime.now() - update_time).days
                if days_old > 7:
                    mismatches.append(f"Context is {days_old} days old")
                if self.dry_run:
                    print(f"Last Update: {last_update} ({days_old} days old)")

            # Check security context
            sec_context = self.session_graph.value(None, SESSION.securityContext, None)
            if not sec_context:
                mismatches.append("Missing security context")
            elif self.dry_run:
                print(f"Security Context: {sec_context}")

            # Check cursor rules validity
            rules = list(self.session_graph.objects(None, SESSION.activeCursorRules))
            if rules:
                invalid_rules = [
                    rule
                    for rule in rules
                    if not any(
                        self.session_graph.triples(
                            (rule, RDF.type, SESSION.CursorRule)
                        )  # noqa: E501
                    )
                ]
                if invalid_rules:
                    msg = f"Invalid cursor rules: {invalid_rules}"  # noqa: E501
                    mismatches.append(msg)
                if self.dry_run:
                    print(f"Active Cursor Rules: {rules}")

            if self.dry_run:
                if mismatches:
                    print("\nDetected Mismatches:")
                    for m in mismatches:
                        print(f"- {m}")
                else:
                    print("\nNo context mismatches detected.")

            return "; ".join(mismatches) if mismatches else None

        except Exception as e:
            error = f"Error checking context: {str(e)}"
            if self.dry_run:
                print(f"\nError: {error}")
            return error

    def get_current_context(self) -> Dict[str, Any]:
        """Get the current context from session.ttl"""
        if self.dry_run:
            print("\n=== Getting Current Context (Dry Run) ===")
            print("Current Graph Size:", len(self.session_graph))

        # Check for context issues
        mismatch = self.detect_context_mismatch()
        if mismatch:
            print(f"\nWarning: Possible context mismatch detected: {mismatch}")
            print("Consider creating a new context if this seems incorrect.")

        context_prompt = f"""
        Given the following Turtle RDF from session.ttl, extract and format
        the current context:

        {self.session_graph.serialize(format="turtle")}

        Return a structured description of the current context including:
        1. Active task
        2. Active ontologies
        3. Active cursor rules
        4. Security context
        5. Environment state
        6. Last update timestamp

        Format the response as a clear, hierarchical structure.
        """

        if self.dry_run:
            print("\nPrompt to be sent:")
            print(context_prompt)
            print("\nThis would be sent to Claude for processing...")
            return {"dry_run": True, "prompt": context_prompt}

        response = self.client.messages.create(
            model="claude-3-sonnet-20240229",
            max_tokens=1000,
            temperature=0,
            system=(
                "You are a semantic web expert. Extract and format the current context from the "  # noqa: E501
                "provided session.ttl content."
            ),
            messages=[{"role": "user", "content": context_prompt}],
        )

        self._track_usage(response, "get_current_context")
        return response.content

    def list_contexts(self) -> List[Dict[str, Any]]:
        """List all contexts in the session log with their identifiers"""
        # Query the graph for all entries
        entries = []
        for entry in self.log_graph.subjects(RDF.type, None):
            entry_id = str(entry).split("#")[-1]
            if not entry_id.startswith(
                "http"
            ):  # Skip entries with full URIs  # noqa: E501
                entry_data = {
                    "id": entry_id,
                    "timestamp": str(
                        self.log_graph.value(entry, GUIDANCE.hasTimestamp) or ""
                    ),
                    "actor": str(self.log_graph.value(entry, GUIDANCE.hasActor) or ""),
                    "reason": str(
                        self.log_graph.value(entry, GUIDANCE.hasChangeReason) or ""
                    ),
                    "state": {},
                }

                # Get state information
                for pred, obj in self.log_graph.predicate_objects(entry):  # noqa: E501
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
        current_context = self.session_graph.value(None, RDF.type, SESSION.ContextState)
        if current_context:
            for pred, obj in self.session_graph.predicate_objects(
                current_context
            ):  # noqa: E501
                pred_str = str(pred).split("#")[-1]
                if pred_str in [
                    "activeCursorRules",
                    "activeOntologies",
                    "configurationFiles",
                ]:
                    # Handle list values
                    values = [
                        str(o).split("#")[-1]
                        for o in self.session_graph.objects(current_context, pred)
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

    def pop_context(self) -> Dict[str, Any]:
        """
        Push current context to log and restore previous context
        Returns the restored context
        """
        # First, get the current context
        current_context = self.get_current_context()

        # Create a new log entry for the current context
        timestamp = datetime.utcnow().isoformat() + "Z"
        entry_id = f"entry_{datetime.utcnow().strftime('%Y_%m_%d_%H%M%S')}"

        # Generate log entry prompt
        push_prompt = f"""
        Given the current context:
        {current_context}

        Generate Turtle RDF for session_log.ttl with:
        1. Entry ID: {entry_id}
        2. Timestamp: {timestamp}
        3. Actor: ClaudeAI
        4. Current state preservation

        Start with @prefix declarations.
        """

        push_response = self.client.messages.create(
            model="claude-3-sonnet-20240229",
            max_tokens=1000,
            temperature=0,
            system=(
                "You are a semantic web expert. Generate ONLY Turtle RDF with no markdown"  # noqa: E501
                " or other formatting."
            ),
            messages=[{"role": "user", "content": push_prompt}],  # noqa: E501
        )

        # Get the previous context from the log
        restore_prompt = f"""
        Given the session log:
        {self.log_graph.serialize(format="turtle")}

        Generate Turtle RDF to restore previous context to session.ttl.
        Include all necessary triples and references.

        Start with @prefix declarations.
        """

        restore_response = self.client.messages.create(
            model="claude-3-sonnet-20240229",
            max_tokens=1000,
            temperature=0,
            system=(
                "You are a semantic web expert. Generate ONLY Turtle RDF with no markdown"  # noqa: E501
                " or other formatting."
            ),
            messages=[{"role": "user", "content": restore_prompt}],  # noqa: E501
        )

        # Update both files
        self.update_session_and_log(push_response.content, restore_response.content)

        return self.get_current_context()

    def search_contexts(self, query: str) -> List[Dict[str, Any]]:
        """Search contexts based on arbitrary criteria using LLM"""
        search_prompt = f"""
        Given the following session log content and search query: "{query}"

        {self.log_graph.serialize(format="turtle")}

        Find and rank relevant context entries based on the query.
        Consider semantic similarity and contextual relevance.
        Format results as a list of matches with relevance explanations.
        """

        response = self.client.messages.create(
            model="claude-3-sonnet-20240229",
            max_tokens=1500,
            temperature=0,
            system=(
                "You are a semantic web expert. Search and rank context entries based on"  # noqa: E501
                " the query."
            ),
            messages=[{"role": "user", "content": search_prompt}],  # noqa: E501
        )

        return response.content

    def restore_context(self, context_id: str) -> Dict[str, Any]:
        """Restore a specific context by its ID"""
        restore_prompt = f"""
        Given the session log and context ID: {context_id}

        {self.log_graph.serialize(format="turtle")}

        Generate Turtle RDF to restore context {context_id} to session.ttl.
        Include all necessary triples and references.

        Start with @prefix declarations.
        """

        response = self.client.messages.create(
            model="claude-3-sonnet-20240229",
            max_tokens=1000,
            temperature=0,
            system=(
                "You are a semantic web expert. Generate ONLY Turtle RDF with no markdown"  # noqa: E501
                " or other formatting."
            ),
            messages=[{"role": "user", "content": restore_prompt}],  # noqa: E501
        )

        self.update_session_and_log(None, response.content)
        return self.get_current_context()

    def _extract_text(self, response) -> str:
        """Extract text content from a Claude response"""
        # First get the raw text
        if isinstance(response, list):
            text = str(response[0].text)
        elif hasattr(response, "text"):
            text = str(response.text)
        elif hasattr(response, "content"):
            content = response.content
            if isinstance(content, list):
                text = str(content[0].text)
            else:
                text = str(content)
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

    def update_session_and_log(self, log_update: Optional[str], session_update: str):
        """Update both session.ttl and session_log.ttl with new content"""
        if self.dry_run:
            print("\n=== Dry Run: Proposed Updates ===")
            if log_update:
                print("\nLog Update:")
                print(log_update)
            print("\nSession Update:")
            print(session_update)
            return

        if log_update:
            # Parse and add new log entry
            log_graph = Graph()
            log_text = self._extract_text(log_update)
            log_graph.parse(data=log_text, format="turtle")
            self.log_graph += log_graph

        # Update session with restored context
        session_graph = Graph()
        session_text = self._extract_text(session_update)
        session_graph.parse(data=session_text, format="turtle")
        self.session_graph = session_graph

        # Save both files
        self.save_graphs()

    def format_context_json(self, context_data: Any) -> Dict[str, Any]:
        """Convert context data to JSON format"""
        # Handle TextBlock objects
        if hasattr(context_data, "text"):
            context_data = context_data.text
        elif isinstance(context_data, list) and hasattr(context_data[0], "text"):
            context_data = context_data[0].text

        # Parse the text response into structured data
        if isinstance(context_data, str):
            lines = context_data.split("\n")
        else:
            lines = str(context_data).split("\n")

        result = {"contexts": [], "current_state": {}}
        current_context = None
        in_state_summary = False

        for line in lines:
            line = line.strip()
            if not line:
                continue

            # Handle context entries
            if line.startswith("Entry ID:"):
                if current_context:
                    result["contexts"].append(current_context)
                current_context = {"id": line.split(":", 1)[1].strip()}
            elif current_context and line.startswith("Timestamp:"):
                current_context["timestamp"] = line.split(":", 1)[1].strip()
            elif current_context and line.startswith("Actor:"):
                current_context["actor"] = line.split(":", 1)[1].strip()
            elif current_context and line.startswith("Change Reason:"):  # noqa: E501
                current_context["reason"] = line.split(":", 1)[1].strip()
            elif line.startswith("State summary:"):
                in_state_summary = True
                if current_context:
                    current_context["state"] = {}
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

                if current_context:
                    current_context["state"][key] = value
                else:
                    result["current_state"][key] = value

        # Add the last context if any
        if current_context:
            result["contexts"].append(current_context)

        return result


def format_output(
    data: Dict[str, Any], pretty: bool = False, color: bool = True
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
        "param", nargs="?", help="Parameter for search/restore commands"
    )
    parser.add_argument(
        "-p", "--pretty", action="store_true", help="Pretty print output"
    )
    parser.add_argument(
        "--no-color", action="store_true", help="Disable colored output"
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
            result = manager.list_contexts()  # Already returns a dictionary
        elif args.command == "pop":
            result = manager.pop_context()
            result = manager.format_context_json(result)  # Convert text to JSON
        elif args.command == "search" and args.param:
            result = manager.search_contexts(args.param)
            result = manager.format_context_json(result)  # Convert text to JSON
        elif args.command == "restore" and args.param:
            result = manager.restore_context(args.param)
            result = manager.format_context_json(result)  # Convert text to JSON
        else:
            print("Invalid command or missing parameter")
            return

        # Format and display output
        format_output(result, pretty=args.pretty, color=not args.no_color)  # noqa: E501

    except Exception as e:
        print(f"Error: {str(e)}")
        sys.exit(1)


if __name__ == "__main__":
    main()
