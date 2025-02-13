#!/usr/bin/env python3
"""
Wrapper for Apache Jena tools to handle ontology processing.
Assumes Jena is installed and available in the system path.
"""

import json
import os
import subprocess
import tempfile
from pathlib import Path


class JenaTools:
    def __init__(self):
        # Verify Jena installation
        try:
            subprocess.run(
                ["riot", "--version"], capture_output=True, check=True
            )
        except subprocess.CalledProcessError:
            raise RuntimeError(
                "Apache Jena RIOT tool not found. Please ensure Jena is installed and in PATH."
            )

    def validate_ttl(self, ttl_file: str) -> tuple[bool, str]:
        """Validate a Turtle file using Jena's RIOT."""
        try:
            result = subprocess.run(
                ["riot", "--validate", ttl_file],
                capture_output=True,
                text=True,
                check=True,
            )
            return True, "Validation successful"
        except subprocess.CalledProcessError as e:
            return False, e.stderr

    def run_sparql(self, ttl_file: str, query: str) -> list[dict]:
        """Run a SPARQL query against a Turtle file using Jena's SPARQL query tool."""
        # Write query to temporary file
        with tempfile.NamedTemporaryFile(
            mode="w", suffix=".rq", delete=False
        ) as f:
            f.write(query)
            query_file = f.name

        try:
            # Run query using sparql command line tool
            result = subprocess.run(
                [
                    "sparql",
                    "--data",
                    ttl_file,
                    "--query",
                    query_file,
                    "--results",
                    "json",
                ],
                capture_output=True,
                text=True,
                check=True,
            )

            # Parse JSON results
            results = json.loads(result.stdout)
            return results.get("results", {}).get("bindings", [])
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
        dep_query = (
            prefixes
            + """
        SELECT ?source ?target ?sourceLabel ?targetLabel
        WHERE {
            ?source deploy:dependsOn ?target ;
                    rdfs:label ?sourceLabel .
            ?target rdfs:label ?targetLabel .
        }
        ORDER BY ?sourceLabel ?targetLabel
        """
        )
        relationships["dependencies"] = self.run_sparql(ttl_file, dep_query)

        # Configurations query
        config_query = (
            prefixes
            + """
        SELECT ?config ?component ?configLabel ?componentLabel
        WHERE {
            ?config deploy:configures ?component ;
                    rdfs:label ?configLabel .
            ?component rdfs:label ?componentLabel .
        }
        ORDER BY ?configLabel ?componentLabel
        """
        )
        relationships["configurations"] = self.run_sparql(
            ttl_file, config_query
        )

        # Emulations query
        emul_query = (
            prefixes
            + """
        SELECT ?local ?azure ?localLabel ?azureLabel
        WHERE {
            ?local deploy:emulates ?azure ;
                   rdfs:label ?localLabel .
            ?azure rdfs:label ?azureLabel .
        }
        ORDER BY ?localLabel ?azureLabel
        """
        )
        relationships["emulations"] = self.run_sparql(ttl_file, emul_query)

        # Used In query
        used_query = (
            prefixes
            + """
        SELECT ?component ?env ?componentLabel ?envLabel
        WHERE {
            ?component deploy:usedIn ?env ;
                      rdfs:label ?componentLabel .
            ?env rdfs:label ?envLabel .
        }
        ORDER BY ?componentLabel ?envLabel
        """
        )
        relationships["used_in"] = self.run_sparql(ttl_file, used_query)

        return relationships

    def get_status(self, ttl_files: list[str] = None) -> dict:
        """Get comprehensive status from the ontology files."""
        if ttl_files is None:
            ttl_files = ["session.ttl", "deployment.ttl"]

        status = {
            "implementation": [],
            "deployment": [],
            "security": [],
            "validation": [],
        }

        # Common prefixes for all queries
        prefixes = """
        PREFIX rdf: <http://www.w3.org/1999/02/22-rdf-syntax-ns#>
        PREFIX rdfs: <http://www.w3.org/2000/01/rdf-schema#>
        PREFIX owl: <http://www.w3.org/2002/07/owl#>
        PREFIX deploy: <./deployment#>
        PREFIX session: <./session#>
        PREFIX chatbot: <./chatbot#>
        """

        # Implementation Status Query
        impl_query = (
            prefixes
            + """
        SELECT DISTINCT ?implementation ?label ?status ?environment ?lastUpdated
        WHERE {
            ?implementation a session:ImplementationArtifact ;
                          rdfs:label ?label ;
                          session:validationStatus ?status .
            OPTIONAL { ?implementation session:lastValidated ?lastUpdated }
            OPTIONAL { ?implementation session:deploymentEnvironment ?environment }
        }
        ORDER BY ?label
        """
        )

        # Deployment Status Query
        deploy_query = (
            prefixes
            + """
        SELECT ?deployment ?type ?status ?endpoint ?lastUpdated
        WHERE {
            ?deployment a session:Deployment ;
                       session:deploymentType ?type ;
                       session:status ?status .
            OPTIONAL { ?deployment session:endpoint ?endpoint }
            OPTIONAL { ?deployment session:lastUpdated ?lastUpdated }
        }
        """
        )

        # Security Status Query
        security_query = (
            prefixes
            + """
        SELECT ?component ?requirement ?status ?lastChecked
        WHERE {
            ?component session:hasSecurityRequirement ?requirement .
            ?requirement session:validationStatus ?status .
            OPTIONAL { ?requirement session:lastChecked ?lastChecked }
        }
        """
        )

        # Validation Status Query
        validation_query = (
            prefixes
            + """
        SELECT ?validation ?type ?status ?lastRun
        WHERE {
            ?validation a session:ValidationRequirement ;
                       session:validationType ?type ;
                       session:completionStatus ?status .
            OPTIONAL { ?validation session:lastValidated ?lastRun }
        }
        """
        )

        for ttl_file in ttl_files:
            try:
                # Run all queries and collect results
                status["implementation"].extend(
                    self.run_sparql(ttl_file, impl_query)
                )
                status["deployment"].extend(
                    self.run_sparql(ttl_file, deploy_query)
                )
                status["security"].extend(
                    self.run_sparql(ttl_file, security_query)
                )
                status["validation"].extend(
                    self.run_sparql(ttl_file, validation_query)
                )
            except Exception as e:
                print(f"Warning: Error processing {ttl_file}: {e}")

        return status

    def format_status_output(self, status: dict) -> str:
        """Format status results into a readable string."""
        output = []

        output.append("=== Implementation Status ===")
        for impl in status["implementation"]:
            output.append(
                f"\n• {impl.get('label', {}).get('value', 'Unknown')}:"
            )
            output.append(
                f"  Status: {impl.get('status', {}).get('value', 'Unknown')}"
            )
            if "lastUpdated" in impl:
                output.append(
                    f"  Last Updated: {impl['lastUpdated']['value']}"
                )
            if "environment" in impl and impl["environment"].get("value"):
                output.append(
                    f"  Environment: {impl['environment']['value']}"
                )

        output.append("\n=== Deployment Status ===")
        for deploy in status["deployment"]:
            output.append(
                f"\n• {deploy.get('type', {}).get('value', 'Unknown')}:"
            )
            output.append(
                f"  Status: {deploy.get('status', {}).get('value', 'Unknown')}"
            )
            if "endpoint" in deploy:
                output.append(f"  Endpoint: {deploy['endpoint']['value']}")
            if "lastUpdated" in deploy and deploy["lastUpdated"].get("value"):
                output.append(
                    f"  Last Updated: {deploy['lastUpdated']['value']}"
                )

        output.append("\n=== Security Status ===")
        for sec in status["security"]:
            output.append(
                f"\n• {sec.get('requirement', {}).get('value', 'Unknown')}:"
            )
            output.append(
                f"  Status: {sec.get('status', {}).get('value', 'Unknown')}"
            )
            if "lastChecked" in sec:
                output.append(
                    f"  Last Checked: {sec['lastChecked']['value']}"
                )

        output.append("\n=== Validation Status ===")
        for val in status["validation"]:
            output.append(
                f"\n• {val.get('type', {}).get('value', 'Unknown')}:"
            )
            output.append(
                f"  Status: {val.get('status', {}).get('value', 'Unknown')}"
            )
            if "lastRun" in val:
                output.append(f"  Last Run: {val['lastRun']['value']}")

        return "\n".join(output)


def main():
    """Test the Jena tools wrapper."""
    jena = JenaTools()

    # Test with deployment.ttl
    ttl_file = "deployment.ttl"

    # Validate TTL file
    valid, msg = jena.validate_ttl(ttl_file)
    print(f"Validation {'successful' if valid else 'failed'}: {msg}")

    # Get and print relationships
    relationships = jena.get_relationships(ttl_file)

    print("\nDependencies:")
    for rel in relationships["dependencies"]:
        print(
            f"{rel['sourceLabel']['value']} -> {rel['targetLabel']['value']}"
        )

    print("\nConfigurations:")
    for rel in relationships["configurations"]:
        print(
            f"{rel['configLabel']['value']} -> {rel['componentLabel']['value']}"
        )

    print("\nEmulations:")
    for rel in relationships["emulations"]:
        print(f"{rel['localLabel']['value']} -> {rel['azureLabel']['value']}")

    print("\nUsed In:")
    for rel in relationships["used_in"]:
        print(
            f"{rel['componentLabel']['value']} -> {rel['envLabel']['value']}"
        )


if __name__ == "__main__":
    main()
