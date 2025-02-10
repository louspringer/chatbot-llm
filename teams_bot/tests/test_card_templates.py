"""
# Ontology: cortexteams:CardTemplatesTest
# Implements: cortexteams:AdaptiveCards
# Requirement: REQ-BOT-002 Teams card templates
# Guidance: guidance:BotPatterns#CardTemplates
# Description: Tests for Teams Adaptive Card templates
"""

from teams_bot.bot.card_templates import (
    AdaptiveCardTemplate,
    WelcomeCard,
    QueryResultCard,
    ErrorCard,
    FormCard
)


def test_base_card_structure():
    """Test the base card structure."""
    body = [{"type": "TextBlock", "text": "Test"}]
    card = AdaptiveCardTemplate.create_base_card(body)
    
    assert card["type"] == "AdaptiveCard"
    assert card["$schema"] == AdaptiveCardTemplate.SCHEMA
    assert card["version"] == AdaptiveCardTemplate.VERSION
    assert card["body"] == body


def test_welcome_card():
    """Test welcome card creation."""
    user_name = "Test User"
    card = WelcomeCard.create(user_name)
    
    assert card["type"] == "AdaptiveCard"
    body = card["body"]
    
    # Check welcome message
    assert body[0]["text"] == f"Welcome {user_name}! 👋"
    assert body[0]["type"] == "TextBlock"
    
    # Check description
    assert "Teams Bot" in body[1]["text"]
    assert body[1]["wrap"] is True
    
    # Check actions
    actions = body[2]["actions"]
    assert len(actions) == 2
    assert actions[0]["title"] == "Get Started"
    assert actions[1]["title"] == "View Tutorial"


def test_form_card():
    """Test form card creation."""
    title = "Test Form"
    fields = [
        FormCard.create_text_input(
            "name",
            "Full Name",
            "Enter your name",
            True
        ),
        FormCard.create_choice_set(
            "role",
            "Role",
            [
                {"title": "Admin", "value": "admin"},
                {"title": "User", "value": "user"}
            ],
            True
        )
    ]
    
    card = FormCard.create(title, fields)
    body = card["body"]
    
    # Check title
    assert body[0]["text"] == title
    assert body[0]["type"] == "TextBlock"
    
    # Check fields container
    container = body[1]
    assert container["type"] == "Container"
    assert len(container["items"]) == 2
    
    # Check text input
    text_input = container["items"][0]
    assert text_input["type"] == "Input.Text"
    assert text_input["id"] == "name"
    assert text_input["isRequired"] is True
    
    # Check choice set
    choice_set = container["items"][1]
    assert choice_set["type"] == "Input.ChoiceSet"
    assert choice_set["id"] == "role"
    assert len(choice_set["choices"]) == 2
    
    # Check actions
    actions = body[2]["actions"]
    assert len(actions) == 2
    assert actions[0]["title"] == "Submit"
    assert actions[1]["title"] == "Cancel"


def test_form_card_text_input():
    """Test form card text input creation."""
    text_input = FormCard.create_text_input(
        "test_id",
        "Test Label",
        "Test Placeholder",
        True,
        100
    )
    
    assert text_input["type"] == "Input.Text"
    assert text_input["id"] == "test_id"
    assert text_input["label"] == "Test Label"
    assert text_input["placeholder"] == "Test Placeholder"
    assert text_input["isRequired"] is True
    assert text_input["maxLength"] == 100


def test_form_card_choice_set():
    """Test form card choice set creation."""
    choices = [
        {"title": "Option 1", "value": "1"},
        {"title": "Option 2", "value": "2"}
    ]
    
    choice_set = FormCard.create_choice_set(
        "test_id",
        "Test Label",
        choices,
        True,
        True
    )
    
    assert choice_set["type"] == "Input.ChoiceSet"
    assert choice_set["id"] == "test_id"
    assert choice_set["label"] == "Test Label"
    assert choice_set["isRequired"] is True
    assert choice_set["isMultiSelect"] is True
    assert len(choice_set["choices"]) == 2
    assert choice_set["choices"][0]["title"] == "Option 1"
    assert choice_set["choices"][0]["value"] == "1"


def test_query_result_card_with_data():
    """Test query result card with data."""
    title = "Test Results"
    results = [
        {"name": "John", "age": 30},
        {"name": "Jane", "age": 25}
    ]
    
    card = QueryResultCard.create(title, results)
    body = card["body"]
    
    # Check title
    assert body[0]["text"] == title
    
    # Check headers
    header_set = body[1]
    assert header_set["type"] == "ColumnSet"
    headers = header_set["columns"]
    assert len(headers) == 2
    assert headers[0]["items"][0]["text"] == "name"
    assert headers[1]["items"][0]["text"] == "age"
    
    # Check data rows
    data_row = body[2]
    assert data_row["type"] == "ColumnSet"
    row_data = data_row["columns"]
    assert row_data[0]["items"][0]["text"] == "John"
    assert row_data[1]["items"][0]["text"] == "30"


def test_query_result_card_empty_data():
    """Test query result card with empty data."""
    card = QueryResultCard.create("Empty Results", [], [])
    body = card["body"]
    
    # Should still have title and export action
    assert len(body) == 3
    assert body[0]["text"] == "Empty Results"
    assert body[-1]["type"] == "ActionSet"


def test_error_card():
    """Test error card creation."""
    error_msg = "Test error message"
    error_id = "ERR-123"
    
    card = ErrorCard.create(error_msg, error_id)
    body = card["body"]
    
    # Check error header
    assert body[0]["text"] == "⚠️ Error"
    assert body[0]["color"] == "Attention"
    
    # Check error message
    assert body[1]["text"] == error_msg
    assert body[1]["wrap"] is True
    
    # Check error ID
    assert body[2]["text"] == f"Reference ID: {error_id}"
    assert body[2]["isSubtle"] is True
    
    # Check actions
    actions = body[3]["actions"]
    assert len(actions) == 2
    assert actions[0]["title"] == "Try Again"
    assert actions[1]["title"] == "Get Help"


def test_error_card_without_id():
    """Test error card without error ID."""
    error_msg = "Test error message"
    card = ErrorCard.create(error_msg)
    body = card["body"]
    
    # Should not include error ID block
    assert len(body) == 3
    assert all(
        "Reference ID" not in str(block.get("text", ""))
        for block in body) 