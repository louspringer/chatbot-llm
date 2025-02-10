#!/usr/bin/env python3
"""
Visualization engine for generating architecture diagrams from ontology files.
Uses PlantUML for diagram generation.
"""

import argparse
import os
import subprocess
from pathlib import Path
from rdflib import Graph, Namespace, URIRef
from rdflib.namespace import RDF, RDFS, OWL

def get_workspace_uri():
    """Get the workspace URI using the current working directory."""
    workspace_path = Path.cwd()
    return f"file://{workspace_path}/"

class OntologyVisualizer:
    def __init__(self, ontology_path):
        self.graph = Graph()
        
        # Create namespace relative to workspace
        workspace_uri = get_workspace_uri()
        self.DEPLOY = Namespace(f"{workspace_uri}deployment#")
        
        # Bind the namespace
        self.graph.bind('deploy', self.DEPLOY)
        self.graph.parse(ontology_path, format="turtle")
        
    def get_local_name(self, uri_ref):
        """Extract local name from URIRef, handling both relative and absolute URIs."""
        uri_str = str(uri_ref)
        if '#' in uri_str:
            return uri_str.split('#')[1]
        return uri_str.split('/')[-1]
        
    def generate_plantuml(self):
        """Generate PlantUML diagram from ontology."""
        puml = []
        puml.append("@startuml deployment_architecture")
        
        # Define colors
        puml.append("!define AZURE_COLOR #0072C6")
        puml.append("!define LOCAL_COLOR #4CAF50")
        puml.append("!define SHARED_COLOR #9C27B0")
        
        # Style settings
        puml.extend([
            "skinparam component {",
            "    BackgroundColor<<azure>> AZURE_COLOR",
            "    BackgroundColor<<local>> LOCAL_COLOR",
            "    BackgroundColor<<shared>> SHARED_COLOR",
            "    FontColor<<azure>> white",
            "    FontColor<<local>> white",
            "    FontColor<<shared>> white",
            "}",
            ""
        ])
        
        # Title as a note
        puml.extend([
            'note as Title',
            '  = Teams Bot Deployment Architecture',
            '  Local Development & Azure Development',
            'end note',
            ''
        ])
        
        # Color legend
        puml.extend([
            'note as N1',
            '  Color Legend:',
            '  <back:AZURE_COLOR>Azure-specific</back>',
            '  <back:LOCAL_COLOR>Local-specific</back>',
            '  <back:SHARED_COLOR>Shared Components</back>',
            'end note',
            ''
        ])
        
        # Shared Core Components
        puml.append('package "Shared Core Components" <<shared>> {')
        for component in self.graph.subjects(RDF.type, self.DEPLOY.SharedComponent):
            label = str(list(self.graph.objects(component, RDFS.label))[0])
            puml.append(f'    component "{label}" as {self.get_local_name(component)} <<shared>>')
            
            # Add notes for specific components
            if "State Manager" in label:
                puml.extend([
                    '    note right of StateManager',
                    '        Identical state management logic',
                    '        used in both environments',
                    '    end note'
                ])
        puml.append('}')
        puml.append('')
        
        # Configuration Components
        puml.append('package "Configuration" <<shared>> {')
        for component in self.graph.subjects(RDF.type, self.DEPLOY.ConfigurationComponent):
            label = str(list(self.graph.objects(component, RDFS.label))[0])
            puml.append(f'    component "{label}" as {self.get_local_name(component)} <<shared>>')
            
            # Add note for host.json
            if "host.json" in label:
                puml.extend([
                    '    note right of HostJson',
                    '        Shared configuration files',
                    '        ensure consistent behavior',
                    '    end note'
                ])
        puml.append('}')
        puml.append('')
        
        # Azure Components
        puml.append('package "Azure Development Environment" <<azure>> {')
        for component in self.graph.subjects(RDF.type, self.DEPLOY.InfrastructureComponent):
            label = str(list(self.graph.objects(component, RDFS.label))[0])
            puml.append(f'    component "{label}" as {self.get_local_name(component)} <<azure>>')
            
            # Add note for Functions App
            if "Functions App" in label:
                puml.extend([
                    '    note right of FunctionsApp',
                    '        Production-grade components',
                    '        with full Azure integration',
                    '    end note'
                ])
        puml.append('}')
        puml.append('')
        
        # Local Components
        puml.append('package "Local Development Environment" <<local>> {')
        for component in self.graph.subjects(RDF.type, self.DEPLOY.LocalComponent):
            label = str(list(self.graph.objects(component, RDFS.label))[0])
            puml.append(f'    component "{label}" as {self.get_local_name(component)} <<local>>')
            
            # Add note for Core Tools
            if "Core Tools" in label:
                puml.extend([
                    '    note right of CoreTools',
                    '        Development tools that',
                    '        simulate Azure services',
                    '    end note'
                ])
        puml.append('}')
        puml.append('')
        
        # Runtime Dependencies
        puml.append('package "Runtime Dependencies" <<shared>> {')
        for component in self.graph.subjects(RDF.type, self.DEPLOY.RuntimeDependency):
            label = str(list(self.graph.objects(component, RDFS.label))[0])
            puml.append(f'    component "{label}" as {self.get_local_name(component)} <<shared>>')
        puml.append('}')
        puml.append('')
        
        # Relationships
        # Shared Core to Both Environments
        for s, p, o in self.graph.triples((None, self.DEPLOY.dependsOn, None)):
            s_name = self.get_local_name(s)
            o_name = self.get_local_name(o)
            # Skip runtime dependencies for now to match original layout
            if not any(x in s_name for x in ['Python', 'SDK']):
                puml.append(f'{s_name} --> {o_name}')
        
        # Configuration Usage
        for s, p, o in self.graph.triples((None, self.DEPLOY.configures, None)):
            puml.append(f'{self.get_local_name(s)} --> {self.get_local_name(o)}')
        
        # Emulation relationships
        for s, p, o in self.graph.triples((None, self.DEPLOY.emulates, None)):
            puml.append(f'{self.get_local_name(s)} ..> {self.get_local_name(o)} : emulates')
        
        # Runtime Dependencies (shown last to match original layout)
        for s, p, o in self.graph.triples((None, self.DEPLOY.dependsOn, None)):
            s_name = self.get_local_name(s)
            o_name = self.get_local_name(o)
            if any(x in s_name for x in ['Python', 'SDK']):
                puml.append(f'{s_name} --> {o_name}')
        
        # Additional Notes
        puml.extend([
            'note as SharedNote',
            '  Shared Components (60-70% overlap):',
            '  * Core Bot Logic',
            '  * Configuration',
            '  * Message Processing',
            '  * State Management',
            '  * Error Handling',
            '  * API Endpoints',
            'end note',
            '',
            'note as DifferencesNote',
            '  Key Differences:',
            '  * Infrastructure (Azure vs Local)',
            '  * Storage (Azure Storage vs Azurite)',
            '  * Authentication (Azure AD vs Anonymous)',
            '  * Monitoring (App Insights vs Local Logs)',
            '  * Channel (Teams vs Emulator)',
            'end note'
        ])
        
        puml.append('@enduml')
        return '\n'.join(puml)

def generate_svg(plantuml_content, output_path):
    """Generate SVG using PlantUML."""
    # Ensure the output directory exists
    os.makedirs(os.path.dirname(output_path), exist_ok=True)
    
    # Write PlantUML content to temporary file
    temp_file = "temp.puml"
    with open(temp_file, "w") as f:
        f.write(plantuml_content)
    
    # Generate SVG using PlantUML
    plantuml_jar = os.path.join("tools", "plantuml.jar")
    
    # First verify the jar exists
    if not os.path.exists(plantuml_jar):
        raise RuntimeError(f"PlantUML jar not found at {plantuml_jar}")
    
    # Run PlantUML with explicit output file
    cmd = [
        "java", "-jar", plantuml_jar,
        "-tsvg",  # SVG output format
        "-output", os.path.dirname(output_path),  # Output directory
        "-filename", os.path.basename(output_path),  # Force output filename
        temp_file
    ]
    
    try:
        result = subprocess.run(cmd, capture_output=True, text=True)
        
        if result.returncode != 0:
            print("PlantUML command failed:")
            print(f"Command: {' '.join(cmd)}")
            print(f"Exit code: {result.returncode}")
            print(f"stdout: {result.stdout}")
            print(f"stderr: {result.stderr}")
            print("\nContent of temp.puml:")
            with open(temp_file) as f:
                print(f.read())
            raise RuntimeError("PlantUML failed to generate the diagram")
            
        if not os.path.exists(output_path):
            print(f"PlantUML did not generate the expected file at {output_path}")
            print("Files in output directory:")
            print(subprocess.run(
                ["ls", "-la", os.path.dirname(output_path)], 
                capture_output=True, 
                text=True
            ).stdout)
            raise RuntimeError(
                "PlantUML completed but did not generate the expected file.\n"
                "This could be due to:\n"
                "1. Incorrect @startuml name\n"
                "2. Invalid PlantUML syntax\n"
                "3. Output path permissions\n"
                "Please check the PlantUML content and try again."
            )
    finally:
        # Cleanup
        if os.path.exists(temp_file):
            os.remove(temp_file)

def main():
    parser = argparse.ArgumentParser(description="Generate architecture diagrams from ontology files")
    parser.add_argument("--ontology", required=True, help="Path to ontology file")
    parser.add_argument("--output", required=True, help="Output path for generated diagram")
    args = parser.parse_args()
    
    # Generate diagram
    visualizer = OntologyVisualizer(args.ontology)
    plantuml_content = visualizer.generate_plantuml()
    generate_svg(plantuml_content, args.output)
    print(f"Generated diagram at {args.output}")

if __name__ == "__main__":
    main() 