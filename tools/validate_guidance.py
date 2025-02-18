# Ontology: meta:ValidationComponent
# Implements: meta:GuidanceValidator
# Requirement: REQ-VAL-002 Automated guidance validation
# Guidance: guidance:ValidationPatterns#AutomatedValidation
# Description: Automated validation of guidance compliance and traceability

import logging
from pathlib import Path
from typing import Dict, List

import rdflib


class GuidanceValidator:
    """Validates guidance compliance across the project."""

    def __init__(self, session_file: Path):
        self.g = rdflib.Graph()
        self.g.parse(session_file, format="turtle")
        self.logger = logging.getLogger(__name__)

    def validate_traceability(self) -> List[Dict]:
        """Validates artifact traceability."""
        query = """
        PREFIX rdf: <http://www.w3.org/1999/02/22-rdf-syntax-ns#>
        PREFIX session: <./session#>
        PREFIX guidance: <./guidance#>

        SELECT DISTINCT ?artifact ?missing
        WHERE {
            ?artifact a owl:Class .
            OPTIONAL { ?artifact session:hasTraceabilityHeader ?header }
            BIND(IF(BOUND(?header), "", "Missing header") AS ?missing)
            FILTER(BOUND(?missing))
        }
        """
        results = self.g.query(query)
        return [{"artifact": str(row[0]), "issue": str(row[1])} for row in results]

    def validate_pattern_compliance(self) -> List[Dict]:
        """Validates guidance pattern compliance."""
        query = """
        PREFIX rdf: <http://www.w3.org/1999/02/22-rdf-syntax-ns#>
        PREFIX guidance: <./guidance#>

        SELECT ?component ?pattern
        WHERE {
            ?component a owl:Class .
            ?pattern a guidance:Pattern .
            FILTER NOT EXISTS {
                ?component guidance:implementsPattern ?pattern
            }
        }
        """
        results = self.g.query(query)
        return [
            {"component": str(row[0]), "missing_pattern": str(row[1])}
            for row in results
        ]

    def validate_ontology_references(self) -> List[Dict]:
        """Validates ontology references."""
        query = """
        PREFIX rdf: <http://www.w3.org/1999/02/22-rdf-syntax-ns#>
        PREFIX session: <./session#>

        SELECT ?artifact ?ref
        WHERE {
            ?artifact session:hasOntologyReference ?ref .
            FILTER NOT EXISTS { ?ref a owl:Class }
        }
        """
        results = self.g.query(query)
        return [
            {"artifact": str(row[0]), "invalid_ref": str(row[1])} for row in results
        ]

    def run_all_validations(self) -> Dict[str, List[Dict]]:
        """Runs all validation checks."""
        return {
            "traceability": self.validate_traceability(),
            "pattern_compliance": self.validate_pattern_compliance(),
            "ontology_references": self.validate_ontology_references(),
        }

    def update_session_compliance(self, results: Dict[str, List[Dict]]) -> None:
        """Updates session compliance status."""
        has_issues = any(len(v) > 0 for v in results.values())
        status = "incomplete" if has_issues else "complete"

        update_query = """
        PREFIX session: <./session#>
        DELETE {
            ?compliance session:hasTraceabilityStatus ?oldStatus
        }
        INSERT {
            ?compliance session:hasTraceabilityStatus ?newStatus
        }
        WHERE {
            ?compliance a session:GuidanceCompliance ;
                       session:hasTraceabilityStatus ?oldStatus .
        }
        """
        self.g.update(update_query, initBindings={"newStatus": status})


if __name__ == "__main__":
    validator = GuidanceValidator(Path("session.ttl"))
    results = validator.run_all_validations()
    validator.update_session_compliance(results)

    # Log results
    logging.basicConfig(level=logging.INFO)
    logger = logging.getLogger(__name__)

    for check_type, issues in results.items():
        if issues:
            logger.warning(f"{check_type} validation issues found:")
            for issue in issues:
                logger.warning(f"  {issue}")
        else:
            logger.info(f"{check_type} validation passed")
