"""
# Ontology: cortexteams:CardTemplatesTest
# Implements: cortexteams:AdaptiveCards
# Requirement: REQ-BOT-004 Teams card templates
# Guidance: guidance:BotPatterns#CardTemplates
# Description: Tests for Teams Adaptive Card templates
"""

from teams_bot.bot.card_templates import (
    AdaptiveCardTemplate,
    ErrorCard,
    FormCard,
    QueryResultCard,
    WelcomeCard,
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
    card = WelcomeCard.create("Test User")
    assert card["type"] == AdaptiveCardTemplate.SCHEMA
    assert card["version"] == AdaptiveCardTemplate.VERSION
    assert "Test User" in str(card["body"])


def test_form_card():
    """Test form card creation."""
    title = "Test Form"
    fields = [
        FormCard.create_text_input("name", "Name", "Enter your name", True),
        FormCard.create_choice_set(
            "color",
            "Color",
            [
                {"title": "Red", "value": "red"},
                {"title": "Blue", "value": "blue"},
            ],
        ),
    ]
    card = FormCard.create(title, fields)
    assert card["type"] == AdaptiveCardTemplate.SCHEMA
    assert title in str(card["body"])


def test_form_card_text_input():
    """Test form card text input creation."""
    text_input = FormCard.create_text_input(
        "test_id", "Test Label", "Test Placeholder", True, 100
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
        {"title": "Option 2", "value": "2"},
    ]

    choice_set = FormCard.create_choice_set(
        "test_id", "Test Label", choices, True, True
    )

    assert choice_set["type"] == "Input.ChoiceSet"
    assert choice_set["id"] == "test_id"
    assert choice_set["label"] == "Test Label"
    assert choice_set["isRequired"] is True
    assert choice_set["isMultiSelect"] is True
    assert len(choice_set["choices"]) == 2
    assert choice_set["choices"][0]["title"] == "Option 1"
    assert choice_set["choices"][0]["value"] == "1"


def test_query_result_card():
    """Test query result card creation."""
    title = "Test Results"
    results = [
        {"name": "Item 1", "value": 100},
        {"name": "Item 2", "value": 200},
    ]
    columns = ["name", "value"]
    card = QueryResultCard.create(title, results, columns)
    assert card["type"] == AdaptiveCardTemplate.SCHEMA
    assert title in str(card["body"])


def test_query_result_card_with_data():
    """Test query result card with data."""
    title = "Test Results"
    results = [{"name": "John", "age": 30}, {"name": "Jane", "age": 25}]

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
    error_msg = "Test error"
    error_id = "ERR-001"
    card = ErrorCard.create(error_msg, error_id)
    assert card["type"] == AdaptiveCardTemplate.SCHEMA
    assert error_msg in str(card["body"])
    assert error_id in str(card["body"])


def test_error_card_without_id():
    """Test error card without error ID."""
    error_msg = "Test error message"
    card = ErrorCard.create(error_msg)
    body = card["body"]

    # Should not include error ID block
    assert len(body) == 3
    assert all("Reference ID" not in str(block.get("text", "")) for block in body)
