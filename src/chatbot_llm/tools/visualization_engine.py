"""Visualization engine for generating charts and diagrams.

Ontology: viz:VisualizationEngine
Implements: viz:Visualizer, viz:PlantUMLVisualizer, viz:MatplotlibVisualizer
Requirement: REQ-VIZ-001 Dynamic visualization generation
Guidance: guidance:VisualizationPatterns#VisualizerComponent
Description: Provides visualization capabilities through multiple backends
"""

import base64
import json
import subprocess
import tempfile
from abc import ABC, abstractmethod
from io import BytesIO
from pathlib import Path
from typing import Dict, List, Optional, Union

import matplotlib.pyplot as plt
import pandas as pd
import seaborn as sns


class Visualizer(ABC):
    """Base class for visualization generators."""

    @abstractmethod
    def generate(
        self,
        data: Union[pd.DataFrame, Dict, List],
        options: Optional[Dict] = None,
    ) -> str:
        """Generate visualization."""
        pass

    @abstractmethod
    def validate(self, output: str) -> bool:
        """Validate the generated output."""
        pass


class PlantUMLVisualizer(Visualizer):
    """Generate PlantUML diagrams."""

    def generate(
        self,
        data: Union[pd.DataFrame, Dict, List],
        options: Optional[Dict] = None,
    ) -> str:
        """Generate PlantUML diagram."""
        options = options or {}
        diagram_type = options.get("type", "json")

        if diagram_type == "json":
            return self._generate_json(data)
        elif diagram_type == "pie":
            return self._generate_pie(data)
        elif diagram_type == "sequence":
            return self._generate_sequence(data)
        else:
            raise ValueError(f"Unsupported diagram type: {diagram_type}")

    def _generate_json(self, data: Union[Dict, List]) -> str:
        """Generate JSON diagram."""
        return f"""@startjson
{json.dumps(data, indent=2)}
@endjson"""

    def _generate_pie(self, data: Dict) -> str:
        """Generate pie chart."""
        return f"""@startpie
title {data.get('title', 'Distribution')}
{chr(10).join(f'"{k}" : {v}' for k, v in data.items() if k != 'title')}
@endpie"""

    def _generate_sequence(self, data: List[Dict]) -> str:
        """Generate sequence diagram."""
        steps = [f"{step['from']} -> {step['to']}: {step['message']}" for step in data]
        return f"""@startsequence
{chr(10).join(steps)}
@endsequence"""

    def validate(self, output: str) -> bool:
        """Validate PlantUML output."""
        return (
            output.startswith("@start")
            and output.endswith("@end")
            and len(output.split("\n")) > 2
        )

    def generate_svg(self, puml_content: str) -> Optional[Path]:
        """Generate SVG from PlantUML content."""
        try:
            with tempfile.NamedTemporaryFile(suffix=".puml", delete=False) as f:
                f.write(puml_content.encode())
                puml_file = Path(f.name)

            subprocess.run(["plantuml", "-tsvg", str(puml_file)], check=True)

            svg_file = puml_file.with_suffix(".svg")
            return svg_file if svg_file.exists() else None

        except Exception as e:
            print(f"Error generating SVG: {e}")
            return None


class MatplotlibVisualizer(Visualizer):
    """Generate Matplotlib-based visualizations."""

    def generate(
        self,
        data: Union[pd.DataFrame, Dict, List],
        options: Optional[Dict] = None,
    ) -> str:
        """Generate Matplotlib visualization."""
        options = options or {}
        plot_type = options.get("type", "line")

        if isinstance(data, (Dict, List)):
            df = pd.DataFrame(data)
        else:
            df = data

        plt.figure(figsize=options.get("figsize", (10, 6)))

        if plot_type == "line":
            self._generate_line_plot(df, options)
        elif plot_type == "bar":
            self._generate_bar_plot(df, options)
        elif plot_type == "scatter":
            self._generate_scatter_plot(df, options)
        else:
            raise ValueError(f"Unsupported plot type: {plot_type}")

        # Convert plot to base64 string
        buffer = BytesIO()
        plt.savefig(buffer, format="png")
        plt.close()

        return base64.b64encode(buffer.getvalue()).decode()

    def _generate_line_plot(self, df: pd.DataFrame, options: Dict) -> None:
        """Generate line plot."""
        sns.lineplot(data=df)
        self._apply_styling(options)

    def _generate_bar_plot(self, df: pd.DataFrame, options: Dict) -> None:
        """Generate bar plot."""
        sns.barplot(data=df)
        self._apply_styling(options)

    def _generate_scatter_plot(self, df: pd.DataFrame, options: Dict) -> None:
        """Generate scatter plot."""
        sns.scatterplot(data=df)
        self._apply_styling(options)

    def _apply_styling(self, options: Dict) -> None:
        """Apply plot styling."""
        plt.title(options.get("title", ""))
        plt.xlabel(options.get("xlabel", ""))
        plt.ylabel(options.get("ylabel", ""))

        if options.get("grid", True):
            plt.grid(True, alpha=0.3)

        if options.get("theme"):
            plt.style.use(options["theme"])

    def validate(self, output: str) -> bool:
        """Validate Matplotlib output."""
        try:
            # Attempt to decode base64 string
            base64.b64decode(output)
            return True
        except Exception:
            return False


class VisualizationEngine:
    """Main engine for handling visualizations."""

    def __init__(self):
        self.visualizers = {
            "plantuml": PlantUMLVisualizer(),
            "matplotlib": MatplotlibVisualizer(),
        }

    def generate_visualization(
        self,
        data: Union[pd.DataFrame, Dict, List],
        viz_type: str,
        options: Optional[Dict] = None,
    ) -> Dict[str, Union[str, Path]]:
        """Generate visualization of specified type."""
        if viz_type not in self.visualizers:
            raise ValueError(f"Unsupported visualization type: {viz_type}")

        visualizer = self.visualizers[viz_type]
        output = visualizer.generate(data, options)

        if not visualizer.validate(output):
            raise ValueError(f"Invalid {viz_type} output generated")

        result = {"output": output}

        # Generate additional artifacts for PlantUML
        if viz_type == "plantuml":
            svg_path = visualizer.generate_svg(output)
            if svg_path:
                result["svg_path"] = svg_path

        return result
