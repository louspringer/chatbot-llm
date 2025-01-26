"""Result formatting tools for Cortex-Teams integration."""

import json
import pandas as pd
from typing import Dict, List, Union, Optional
from pathlib import Path
import subprocess
import tempfile
from abc import ABC, abstractmethod

class FormatResult(ABC):
    """Base class for result formatting."""
    
    @abstractmethod
    def format(self, data: Union[pd.DataFrame, Dict, List]) -> str:
        """Format the data into desired output."""
        pass

    @abstractmethod
    def validate(self, formatted_output: str) -> bool:
        """Validate the formatted output meets requirements."""
        pass

class MarkdownFormatter(FormatResult):
    """Format results as Markdown tables."""
    
    def format(self, data: Union[pd.DataFrame, Dict, List]) -> str:
        if isinstance(data, (Dict, List)):
            df = pd.DataFrame(data)
        else:
            df = data
        return df.to_markdown(index=False)

    def validate(self, formatted_output: str) -> bool:
        # Basic validation - check for table markers
        lines = formatted_output.split('\n')
        return len(lines) > 2 and '|' in lines[0] and '|-' in lines[1]

class PlantUMLFormatter(FormatResult):
    """Format results as PlantUML diagrams."""
    
    def __init__(self, diagram_type: str = "json"):
        self.diagram_type = diagram_type
        
    def format(self, data: Union[pd.DataFrame, Dict, List]) -> str:
        if self.diagram_type == "json":
            return self._format_json(data)
        elif self.diagram_type == "pie":
            return self._format_pie(data)
        else:
            raise ValueError(f"Unsupported diagram type: {self.diagram_type}")

    def _format_json(self, data: Union[pd.DataFrame, Dict, List]) -> str:
        json_data = data.to_dict() if isinstance(data, pd.DataFrame) else data
        return f"""@startjson
{json.dumps(json_data, indent=2)}
@endjson"""

    def _format_pie(self, data: Union[pd.DataFrame, Dict, List]) -> str:
        if isinstance(data, pd.DataFrame):
            # Assume first two columns are label and value
            data = dict(zip(data.iloc[:,0], data.iloc[:,1]))
        return f"""@startpie
title Data Distribution
{chr(10).join(f'"{k}" : {v}' for k, v in data.items())}
@endpie"""

    def validate(self, formatted_output: str) -> bool:
        return formatted_output.startswith("@start") and formatted_output.endswith("@end")

    def generate_svg(self, formatted_output: str) -> Optional[Path]:
        """Generate SVG from PlantUML diagram."""
        try:
            with tempfile.NamedTemporaryFile(suffix='.puml', delete=False) as f:
                f.write(formatted_output.encode())
                puml_file = Path(f.name)
            
            # Run PlantUML to generate SVG
            subprocess.run(['plantuml', '-tsvg', str(puml_file)], check=True)
            
            svg_file = puml_file.with_suffix('.svg')
            if svg_file.exists():
                return svg_file
            return None
        except Exception as e:
            print(f"Error generating SVG: {e}")
            return None

class TeamsCardFormatter(FormatResult):
    """Format results as Teams Adaptive Cards."""
    
    def format(self, data: Union[pd.DataFrame, Dict, List]) -> str:
        if isinstance(data, pd.DataFrame):
            return self._format_dataframe(data)
        elif isinstance(data, Dict):
            return self._format_dict(data)
        else:
            return self._format_list(data)

    def _format_dataframe(self, df: pd.DataFrame) -> str:
        columns = [{"type": "Column", "items": [{"type": "TextBlock", "text": col}]} 
                  for col in df.columns]
        rows = []
        for _, row in df.iterrows():
            row_items = [{"type": "Column", "items": [{"type": "TextBlock", "text": str(val)}]} 
                        for val in row]
            rows.append({"type": "ColumnSet", "columns": row_items})
        
        card = {
            "type": "AdaptiveCard",
            "$schema": "http://adaptivecards.io/schemas/adaptive-card.json",
            "version": "1.3",
            "body": [
                {"type": "ColumnSet", "columns": columns},
                *rows
            ]
        }
        return json.dumps(card, indent=2)

    def _format_dict(self, data: Dict) -> str:
        items = [{"type": "TextBlock", "text": f"{k}: {v}"} for k, v in data.items()]
        card = {
            "type": "AdaptiveCard",
            "$schema": "http://adaptivecards.io/schemas/adaptive-card.json",
            "version": "1.3",
            "body": items
        }
        return json.dumps(card, indent=2)

    def _format_list(self, data: List) -> str:
        items = [{"type": "TextBlock", "text": str(item)} for item in data]
        card = {
            "type": "AdaptiveCard",
            "$schema": "http://adaptivecards.io/schemas/adaptive-card.json",
            "version": "1.3",
            "body": items
        }
        return json.dumps(card, indent=2)

    def validate(self, formatted_output: str) -> bool:
        try:
            card = json.loads(formatted_output)
            return (card.get("type") == "AdaptiveCard" and 
                   "$schema" in card and 
                   "version" in card and 
                   "body" in card)
        except json.JSONDecodeError:
            return False

class ResultFormatter:
    """Main formatter class that handles all format types."""
    
    def __init__(self):
        self.formatters = {
            'markdown': MarkdownFormatter(),
            'plantuml': PlantUMLFormatter(),
            'teams_card': TeamsCardFormatter()
        }
    
    def format(self, data: Union[pd.DataFrame, Dict, List], 
               format_type: str,
               generate_artifacts: bool = False) -> Dict[str, Union[str, Path]]:
        """Format data into specified format type."""
        if format_type not in self.formatters:
            raise ValueError(f"Unsupported format type: {format_type}")
            
        formatter = self.formatters[format_type]
        formatted_output = formatter.format(data)
        
        if not formatter.validate(formatted_output):
            raise ValueError(f"Invalid {format_type} output generated")
            
        result = {'formatted_text': formatted_output}
        
        # Generate additional artifacts if requested
        if generate_artifacts and format_type == 'plantuml':
            svg_path = formatter.generate_svg(formatted_output)
            if svg_path:
                result['artifact_path'] = svg_path
                
        return result 