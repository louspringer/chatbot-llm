#!/usr/bin/env python3
"""
Wrapper for Apache Jena tools to handle ontology processing.
Assumes Jena is installed and available in the system path.
"""

import subprocess
import json
from pathlib import Path
import tempfile
import os

class JenaTools:
    def __init__(self):
        # Verify Jena installation
        try:
            subprocess.run(['riot', '--version'], capture_output=True, check=True)
        except subprocess.CalledProcessError:
            raise RuntimeError("Apache Jena RIOT tool not found. Please ensure Jena is installed and in PATH.")

    def validate_ttl(self, ttl_file: str) -> tuple[bool, str]:
        """Validate a Turtle file using Jena's RIOT."""
        try:
            result = subprocess.run(
                ['riot', '--validate', ttl_file],
                capture_output=True,
                text=True,
                check=True
            )
            return True, "Validation successful"
        except subprocess.CalledProcessError as e:
            return False, e.stderr

    def run_sparql(self, ttl_file: str, query: str) -> list[dict]:
        """Run a SPARQL query against a Turtle file using Jena's SPARQL query tool."""
        # Write query to temporary file
        with tempfile.NamedTemporaryFile(mode='w', suffix='.rq', delete=False) as f:
            f.write(query)
            query_file = f.name

        try:
            # Run query using sparql command line tool
            result = subprocess.run(
                ['sparql', '--data', ttl_file, '--query', query_file, '--results', 'json'],
                capture_output=True,
                text=True,
                check=True
            )
            
            # Parse JSON results
            results = json.loads(result.stdout)
            return results.get('results', {}).get('bindings', [])
        finally:
            os.unlink(query_file)

    def get_relationships(self, ttl_file: str) -> dict:
        """Get all relationships from the ontology using SPARQL queries."""
        relationships = {}
        
        # Common prefixes for all queries
        prefixes = """
        PREFIX rdf: <http://www.w3.org/1999/02/22-rdf-syntax-ns#>
        PREFIX rdfs: <http://www.w3.org/2000/01/rdf-schema#>
        PREFIX owl: <http://www.w3.org/2002/07/owl#>
        PREFIX deploy: <file:///Users/lou/Documents/chatbot-llm/deployment#>
        """
        
        # Dependencies query
        dep_query = prefixes + """
        SELECT ?source ?target ?sourceLabel ?targetLabel
        WHERE {
            ?source deploy:dependsOn ?target ;
                    rdfs:label ?sourceLabel .
            ?target rdfs:label ?targetLabel .
        }
        ORDER BY ?sourceLabel ?targetLabel
        """
        relationships['dependencies'] = self.run_sparql(ttl_file, dep_query)
        
        # Configurations query
        config_query = prefixes + """
        SELECT ?config ?component ?configLabel ?componentLabel
        WHERE {
            ?config deploy:configures ?component ;
                    rdfs:label ?configLabel .
            ?component rdfs:label ?componentLabel .
        }
        ORDER BY ?configLabel ?componentLabel
        """
        relationships['configurations'] = self.run_sparql(ttl_file, config_query)
        
        # Emulations query
        emul_query = prefixes + """
        SELECT ?local ?azure ?localLabel ?azureLabel
        WHERE {
            ?local deploy:emulates ?azure ;
                   rdfs:label ?localLabel .
            ?azure rdfs:label ?azureLabel .
        }
        ORDER BY ?localLabel ?azureLabel
        """
        relationships['emulations'] = self.run_sparql(ttl_file, emul_query)
        
        # Used In query
        used_query = prefixes + """
        SELECT ?component ?env ?componentLabel ?envLabel
        WHERE {
            ?component deploy:usedIn ?env ;
                      rdfs:label ?componentLabel .
            ?env rdfs:label ?envLabel .
        }
        ORDER BY ?componentLabel ?envLabel
        """
        relationships['used_in'] = self.run_sparql(ttl_file, used_query)
        
        return relationships

def main():
    """Test the Jena tools wrapper."""
    jena = JenaTools()
    
    # Test with deployment.ttl
    ttl_file = 'deployment.ttl'
    
    # Validate TTL file
    valid, msg = jena.validate_ttl(ttl_file)
    print(f"Validation {'successful' if valid else 'failed'}: {msg}")
    
    # Get and print relationships
    relationships = jena.get_relationships(ttl_file)
    
    print("\nDependencies:")
    for rel in relationships['dependencies']:
        print(f"{rel['sourceLabel']['value']} -> {rel['targetLabel']['value']}")
    
    print("\nConfigurations:")
    for rel in relationships['configurations']:
        print(f"{rel['configLabel']['value']} -> {rel['componentLabel']['value']}")
    
    print("\nEmulations:")
    for rel in relationships['emulations']:
        print(f"{rel['localLabel']['value']} -> {rel['azureLabel']['value']}")
    
    print("\nUsed In:")
    for rel in relationships['used_in']:
        print(f"{rel['componentLabel']['value']} -> {rel['envLabel']['value']}")

if __name__ == '__main__':
    main() 