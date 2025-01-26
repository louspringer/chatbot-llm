#!/usr/bin/env python3
"""Validate ontology files and their dependencies."""
import subprocess


def check_ontology(file_path: str) -> bool:
    """Check if an ontology file is valid and accessible."""
    cmd = [
        "arq",
        "--base=file://$(pwd)/",
        "--data", file_path,
        "--query", "src/chatbot_llm/queries/debug.rq"
    ]
    result = subprocess.run(cmd, capture_output=True, text=True)
    return not bool(result.stderr)


def validate_all():
    """Validate all ontology files and their dependencies."""
    ontologies = [
        "meta.ttl",
        "metameta.ttl", 
        "conversation.ttl",
        "problem.ttl",
        "solution.ttl",
        "chatbot.ttl",
        "cortexteams.ttl",
        "guidance.ttl"
    ]
    
    results = []
    for onto in ontologies:
        valid = check_ontology(onto)
        results.append((onto, valid))
        print(f"Checking {onto}: {'✓' if valid else '✗'}")
    
    return all(valid for _, valid in results)


if __name__ == "__main__":
    validate_all() 