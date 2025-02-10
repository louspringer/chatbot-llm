"""
# Ontology: cortexteams:CardTemplates
# Implements: cortexteams:AdaptiveCards
# Requirement: REQ-BOT-002 Teams card templates
# Guidance: guidance:BotPatterns#CardTemplates
# Description: Teams Adaptive Card templates implementation
"""

from typing import Dict, Any, List, Optional


class AdaptiveCardTemplate:
    """Base class for Adaptive Card templates."""

    SCHEMA = "http://adaptivecards.io/schemas/adaptive-card.json"
    VERSION = "1.3"

    @classmethod
    def create_base_card(cls, body: List[Dict[str, Any]]) -> Dict[str, Any]:
        """Create a base adaptive card structure."""
        return {
            "type": "AdaptiveCard",
            "$schema": cls.SCHEMA,
            "version": cls.VERSION,
            "body": body
        }


class WelcomeCard(AdaptiveCardTemplate):
    """Welcome card template."""

    @classmethod
    def create(cls, user_name: str) -> Dict[str, Any]:
        """Create a welcome card."""
        body = [
            {
                "type": "TextBlock",
                "size": "Medium",
                "weight": "Bolder",
                "text": f"Welcome {user_name}! 👋"
            },
            {
                "type": "TextBlock",
                "text": "I'm your Snowflake Cortex Teams Bot assistant.",
                "wrap": True
            },
            {
                "type": "ActionSet",
                "actions": [
                    {
                        "type": "Action.Submit",
                        "title": "Get Started",
                        "data": {
                            "action": "get_started"
                        }
                    },
                    {
                        "type": "Action.Submit",
                        "title": "View Tutorial",
                        "data": {
                            "action": "view_tutorial"
                        }
                    }
                ]
            }
        ]
        return cls.create_base_card(body)


class FormCard(AdaptiveCardTemplate):
    """Interactive form card template."""

    @classmethod
    def create(
        cls,
        title: str,
        fields: List[Dict[str, Any]],
        submit_label: str = "Submit",
        cancel_label: str = "Cancel"
    ) -> Dict[str, Any]:
        """Create an interactive form card.
        
        Args:
            title: Form title
            fields: List of form field definitions
            submit_label: Label for submit button
            cancel_label: Label for cancel button
        """
        body = [
            {
                "type": "TextBlock",
                "size": "Medium",
                "weight": "Bolder",
                "text": title
            },
            {
                "type": "Container",
                "items": fields
            },
            {
                "type": "ActionSet",
                "actions": [
                    {
                        "type": "Action.Submit",
                        "title": submit_label,
                        "style": "positive",
                        "data": {
                            "action": "form_submit"
                        }
                    },
                    {
                        "type": "Action.Submit",
                        "title": cancel_label,
                        "style": "destructive",
                        "data": {
                            "action": "form_cancel"
                        }
                    }
                ]
            }
        ]
        return cls.create_base_card(body)

    @classmethod
    def create_text_input(
        cls,
        id: str,
        label: str,
        placeholder: str = "",
        is_required: bool = False,
        max_length: Optional[int] = None
    ) -> Dict[str, Any]:
        """Create a text input field."""
        return {
            "type": "Input.Text",
            "id": id,
            "label": label,
            "placeholder": placeholder,
            "isRequired": is_required,
            "maxLength": max_length
        }

    @classmethod
    def create_choice_set(
        cls,
        id: str,
        label: str,
        choices: List[Dict[str, str]],
        is_required: bool = False,
        is_multi_select: bool = False
    ) -> Dict[str, Any]:
        """Create a choice set input field."""
        return {
            "type": "Input.ChoiceSet",
            "id": id,
            "label": label,
            "isRequired": is_required,
            "isMultiSelect": is_multi_select,
            "choices": [
                {
                    "title": choice["title"],
                    "value": choice["value"]
                }
                for choice in choices
            ]
        }


class QueryResultCard(AdaptiveCardTemplate):
    """Query result card template."""

    @classmethod
    def create(
        cls,
        title: str,
        results: List[Dict[str, Any]],
        columns: Optional[List[str]] = None
    ) -> Dict[str, Any]:
        """Create a query result card."""
        if not columns and results:
            columns = list(results[0].keys())
        elif not columns:
            columns = []

        # Create column headers
        header_columns = [
            {
                "type": "Column",
                "width": "auto",
                "items": [{
                    "type": "TextBlock",
                    "text": col,
                    "weight": "Bolder"
                }]
            }
            for col in columns
        ]

        # Create data rows
        data_rows = []
        for row in results:
            row_columns = [
                {
                    "type": "Column",
                    "width": "auto",
                    "items": [{
                        "type": "TextBlock",
                        "text": str(row.get(col, "")),
                        "wrap": True
                    }]
                }
                for col in columns
            ]
            data_rows.append({
                "type": "ColumnSet",
                "columns": row_columns
            })

        body = [
            {
                "type": "TextBlock",
                "size": "Medium",
                "weight": "Bolder",
                "text": title
            },
            {
                "type": "ColumnSet",
                "columns": header_columns
            },
            *data_rows,
            {
                "type": "ActionSet",
                "actions": [
                    {
                        "type": "Action.Submit",
                        "title": "Export Results",
                        "data": {
                            "action": "export_results"
                        }
                    }
                ]
            }
        ]
        return cls.create_base_card(body)


class ErrorCard(AdaptiveCardTemplate):
    """Error card template."""

    @classmethod
    def create(
        cls,
        error_message: str,
        error_id: Optional[str] = None
    ) -> Dict[str, Any]:
        """Create an error card."""
        body = [
            {
                "type": "TextBlock",
                "size": "Medium",
                "weight": "Bolder",
                "color": "Attention",
                "text": "⚠️ Error"
            },
            {
                "type": "TextBlock",
                "text": error_message,
                "wrap": True
            }
        ]

        if error_id:
            body.append({
                "type": "TextBlock",
                "text": f"Reference ID: {error_id}",
                "size": "Small",
                "isSubtle": True
            })

        body.append({
            "type": "ActionSet",
            "actions": [
                {
                    "type": "Action.Submit",
                    "title": "Try Again",
                    "data": {
                        "action": "retry"
                    }
                },
                {
                    "type": "Action.OpenUrl",
                    "title": "Get Help",
                    "url": "https://support.example.com"
                }
            ]
        })

        return cls.create_base_card(body)
