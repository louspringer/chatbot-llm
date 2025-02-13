#!/usr/bin/env python3
"""
Tests for session_context_manager.py
"""

import os
from pathlib import Path
from unittest.mock import Mock, patch

import pytest
from rdflib import Graph, Namespace

from tools.chatbot_llm.session_context_manager import SessionContextManager
from tools.chatbot_llm.session_context_manager import (
    main as session_manager_main,
)

# Constants for testing
TEST_DIR = Path(__file__).parent / "fixtures"
TEST_SESSION_FILE = TEST_DIR / "test_session.ttl"
TEST_SESSION_LOG_FILE = TEST_DIR / "test_session_log.ttl"

# Test data
SAMPLE_SESSION_TTL = """
@prefix rdf: <http://www.w3.org/1999/02/22-rdf-syntax-ns#> .
@prefix rdfs: <http://www.w3.org/2000/01/rdf-schema#> .
@prefix owl: <http://www.w3.org/2002/07/owl#> .
@prefix session: <./session#> .
@prefix chatbot: <./chatbot#> .
@prefix cortexteams: <./cortexteams#> .
@prefix xsd: <http://www.w3.org/2001/XMLSchema#> .

session:currentContext a session:ContextState ;
    session:activeTask session:task6 ;
    session:activeOntologies (
        chatbot:ChatbotLLMOntology
        cortexteams:TeamsOntology
    ) ;
    session:activeCursorRules (
        session:SPARQLQueryRule
        session:BlackFormatterRule
    ) ;
    session:securityContext [
        a session:SecurityContext ;
        session:requiresValidation true ;
        session:securityLevel "High"
    ] ;
    session:lastUpdated "2024-03-20T18:30:00Z"^^xsd:dateTime .
"""

SAMPLE_LOG_TTL = """
@prefix : <./session_log#> .
@prefix rdf: <http://www.w3.org/1999/02/22-rdf-syntax-ns#> .
@prefix rdfs: <http://www.w3.org/2000/01/rdf-schema#> .
@prefix session: <./session#> .
@prefix guidance: <./guidance#> .
@prefix xsd: <http://www.w3.org/2001/XMLSchema#> .

:entry_2024_03_20_001 a guidance:SessionLogEntry ;
    rdfs:label "Initial Session Log Entry" ;
    guidance:hasActor :ClaudeAI ;
    guidance:hasTimestamp "2024-03-20T18:30:00Z"^^xsd:dateTime ;
    guidance:hasChangeReason "Initial state" .
"""


@pytest.fixture
def setup_test_files(tmp_path):
    """Create temporary test files"""
    session_file = tmp_path / "test_session.ttl"
    log_file = tmp_path / "test_session_log.ttl"

    session_file.write_text(SAMPLE_SESSION_TTL)
    log_file.write_text(SAMPLE_LOG_TTL)

    return session_file, log_file


@pytest.fixture
def mock_anthropic():
    """Mock Anthropic client"""
    with patch("anthropic.Client") as mock_client:
        mock_response = Mock()
        mock_response.content = """
@prefix : <./session#> .
@prefix rdf: <http://www.w3.org/1999/02/22-rdf-syntax-ns#> .
@prefix rdfs: <http://www.w3.org/2000/01/rdf-schema#> .
@prefix session: <./session#> .
@prefix guidance: <./guidance#> .
@prefix xsd: <http://www.w3.org/2001/XMLSchema#> .

:test_context a session:Context ;
    session:activeTask :task1 ;
    session:lastUpdated "2024-03-20T18:30:00Z"^^xsd:dateTime .
"""
        mock_client.return_value.messages.create.return_value = mock_response
        yield mock_client


@pytest.fixture
def context_manager(setup_test_files, mock_anthropic):
    """Create SessionContextManager instance with test files"""
    session_file, log_file = setup_test_files
    env = patch.dict(os.environ, {"ANTHROPIC_API_KEY": "test-key"})
    session = patch(
        "tools.chatbot_llm.session_context_manager.SESSION_FILE",
        session_file,
    )
    log = patch(
        "tools.chatbot_llm.session_context_manager.SESSION_LOG_FILE",
        log_file,
    )

    with env, session, log:
        manager = SessionContextManager()
        return manager


@pytest.fixture
def dry_run_manager(setup_test_files, mock_anthropic):
    """Create SessionContextManager instance with dry_run=True"""
    session_file, log_file = setup_test_files
    env = patch.dict(os.environ, {"ANTHROPIC_API_KEY": "test-key"})
    session = patch(
        "tools.chatbot_llm.session_context_manager.SESSION_FILE", session_file
    )
    log = patch(
        "tools.chatbot_llm.session_context_manager.SESSION_LOG_FILE", log_file
    )

    with env, session, log:
        manager = SessionContextManager(dry_run=True)
        return manager


def test_init(context_manager):
    """Test initialization of SessionContextManager"""
    assert isinstance(context_manager.session_graph, Graph)
    assert isinstance(context_manager.log_graph, Graph)


def test_load_graphs(context_manager, setup_test_files):
    """Test loading graphs from files"""
    session_file, log_file = setup_test_files
    context_manager.load_graphs()

    # Verify graphs were loaded
    assert len(context_manager.session_graph) > 0
    assert len(context_manager.log_graph) > 0


def test_save_graphs(context_manager, setup_test_files):
    """Test saving graphs to files"""
    session_file, log_file = setup_test_files

    # Add some test data
    SESSION = Namespace("./session#")
    context_manager.session_graph.add(
        (SESSION.test, SESSION.property, SESSION.value)
    )

    # Save and verify
    context_manager.save_graphs()
    assert session_file.exists()
    assert log_file.exists()


def test_get_current_context(context_manager, mock_anthropic):
    """Test getting current context"""
    result = context_manager.get_current_context()
    assert isinstance(result, str)
    assert ":test_context" in result
    assert "session:Context" in result


def test_list_contexts(context_manager, mock_anthropic):
    """Test listing contexts"""
    result = context_manager.list_contexts()
    assert isinstance(result, str)
    assert ":test_context" in result
    assert "session:Context" in result


def test_pop_context(context_manager, mock_anthropic):
    """Test popping context"""
    result = context_manager.pop_context()
    assert isinstance(result, str)
    assert ":test_context" in result
    assert "session:Context" in result


def test_search_contexts(context_manager, mock_anthropic):
    """Test searching contexts"""
    query = "test query"
    result = context_manager.search_contexts(query)
    assert isinstance(result, str)
    assert ":test_context" in result
    assert "session:Context" in result


def test_restore_context(context_manager, mock_anthropic):
    """Test restoring context"""
    context_id = "test_context_id"
    result = context_manager.restore_context(context_id)
    assert isinstance(result, str)
    assert ":test_context" in result
    assert "session:Context" in result


def test_update_session_and_log(context_manager):
    """Test updating session and log files"""
    log_update = """
    @prefix : <./session_log#> .
    :test_entry a :LogEntry .
    """
    session_update = """
    @prefix : <./session#> .
    :test_context a :Context .
    """

    context_manager.update_session_and_log(log_update, session_update)

    # Verify updates were applied
    assert len(context_manager.log_graph) > 0
    assert len(context_manager.session_graph) > 0


def test_missing_api_key():
    """Test handling of missing API key"""
    with (
        patch.dict(os.environ, clear=True),
        pytest.raises(ValueError, match="ANTHROPIC_API_KEY.*not set"),
    ):
        SessionContextManager()


def test_invalid_file_paths():
    """Test handling of invalid file paths"""
    bad_path = Path("/nonexistent/path")
    env = patch.dict(os.environ, {"ANTHROPIC_API_KEY": "test-key"})
    path = patch(
        "tools.chatbot_llm.session_context_manager.SESSION_FILE",
        bad_path,
    )

    with env, path, pytest.raises(FileNotFoundError):
        manager = SessionContextManager()
        manager.load_graphs()


def test_cli_interface():
    """Test CLI interface"""
    argv = patch("sys.argv", ["session_context_manager.py", "list"])
    mgr = patch(
        "tools.chatbot_llm.session_context_manager.SessionContextManager",
    )

    with argv, mgr as mock_mgr:
        mock_instance = Mock()
        mock_instance.list_contexts.return_value = "Test contexts"
        mock_mgr.return_value = mock_instance

        with patch("builtins.print") as mock_print:
            session_manager_main()
            mock_print.assert_called_with("Test contexts")


@pytest.mark.parametrize(
    "command,expected_method",
    [
        ("list", "list_contexts"),
        ("pop", "pop_context"),
        ("search", "search_contexts"),
        ("restore", "restore_context"),
    ],
)
def test_cli_commands(command, expected_method):
    """Test different CLI commands"""
    test_args = ["session_context_manager.py", command]
    if command in ["search", "restore"]:
        test_args.append("test_param")

    argv = patch("sys.argv", test_args)
    mgr = patch(
        "tools.chatbot_llm.session_context_manager.SessionContextManager"
    )

    with argv, mgr as mock_mgr:
        mock_instance = Mock()
        mock_result = f"Test {command} result"
        getattr(mock_instance, expected_method).return_value = mock_result
        mock_mgr.return_value = mock_instance

        from tools.chatbot_llm.session_context_manager import main

        with patch("builtins.print") as mock_print:
            main()
            assert mock_print.called
