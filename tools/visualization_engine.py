class PlantUMLVisualizer:
    """PlantUML diagram generator.
    
    Implements: :PlantUMLVisualizer
    Uses layout preferences from chatbot.ttl:LayoutPreferences
    """
    
    DEFAULT_LAYOUT_PREFERENCES = {
        'direction': 'left to right',
        'ranksep': 22,
        'nodesep': 13,
        'linetype': 'curve',
        'package_style': 'rectangle',
        'arrow_color': '#666666',
        'arrow_thickness': 0.8,
        'package_inner_margin': 6,
        'padding': 3,
        'component_inner_margin': 4
    }
    
    def __init__(self, layout_preferences=None):
        """Initialize with optional layout preferences."""
        self.layout_preferences = (
            layout_preferences or self.DEFAULT_LAYOUT_PREFERENCES
        )
    
    def apply_layout_settings(self, content: str) -> str:
        """Apply layout preferences to PlantUML content."""
        prefs = self.layout_preferences
        direction = (
            "left to right direction" 
            if prefs['direction'] == 'left to right'
            else 'top to bottom direction'
        )
        
        settings = [
            direction,
            f"skinparam ranksep {prefs['ranksep']}",
            f"skinparam nodesep {prefs['nodesep']}",
            f"skinparam linetype {prefs['linetype']}",
            f"skinparam packageStyle {prefs['package_style']}",
            f"skinparam ArrowColor {prefs['arrow_color']}",
            f"skinparam ArrowThickness {prefs['arrow_thickness']}",
            f"skinparam packageInnerMargin {prefs['package_inner_margin']}",
            f"skinparam padding {prefs['padding']}",
            f"skinparam componentInnerMargin {prefs['component_inner_margin']}"
        ]
        
        # Insert settings after @startuml line
        lines = content.split('\n')
        insert_pos = next(
            i for i, line in enumerate(lines)
            if line.strip().startswith('@startuml')
        ) + 1
        return '\n'.join(lines[:insert_pos] + settings + lines[insert_pos:]) 