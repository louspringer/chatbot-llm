# Contributing to Cortex Teams Chatbot

## Code of Conduct

This project and everyone participating in it is governed by our Code of Conduct. By participating, you are expected to uphold this code. Please report unacceptable behavior to project maintainers.

## How Can I Contribute?

### Reporting Bugs

Before creating bug reports, please check the issue list as you might find out that you don't need to create one. When you are creating a bug report, please include as many details as possible:

* Use a clear and descriptive title
* Describe the exact steps which reproduce the problem
* Provide specific examples to demonstrate the steps
* Describe the behavior you observed after following the steps
* Explain which behavior you expected to see instead and why
* Include screenshots and animated GIFs if possible
* Include error messages and stack traces
* Include version information

### Suggesting Enhancements

Enhancement suggestions are tracked as GitHub issues. When creating an enhancement suggestion, please include:

* Use a clear and descriptive title
* Provide a step-by-step description of the suggested enhancement
* Provide specific examples to demonstrate the steps
* Describe the current behavior and explain which behavior you expected to see instead
* Explain why this enhancement would be useful
* List some other applications where this enhancement exists
* Specify which version you're using
* Specify the name and version of the OS you're using

### Pull Requests

Please follow these steps to have your contribution considered by the maintainers:

1. Follow all instructions in the template
2. Follow the styleguides
3. After you submit your pull request, verify that all status checks are passing

## Development Process

### Setting Up Development Environment

1. Fork the repo
2. Clone your fork
   ```bash
   git clone https://github.com/your-username/chatbot-llm.git
   ```
3. Create conda environment
   ```bash
   conda env create -f environment.yml
   conda activate chatbot-env
   ```
4. Install development dependencies
   ```bash
   pip install -e ".[dev]"
   ```

### Making Changes

1. Create a branch
   ```bash
   git checkout -b feature/your-feature-name
   ```
2. Make your changes
3. Run tests
   ```bash
   pytest tests/
   ```
4. Update documentation
5. Commit your changes
   ```bash
   git commit -m "feat: add your feature description"
   ```

### Commit Message Guidelines

We follow the [Conventional Commits](https://www.conventionalcommits.org/) specification:

* feat: A new feature
* fix: A bug fix
* docs: Documentation only changes
* style: Changes that do not affect the meaning of the code
* refactor: A code change that neither fixes a bug nor adds a feature
* perf: A code change that improves performance
* test: Adding missing tests or correcting existing tests
* build: Changes that affect the build system or external dependencies
* ci: Changes to our CI configuration files and scripts

### Code Style

#### Python
* Follow PEP 8
* Use type hints
* Write docstrings
* Maximum line length of 100 characters
* Use f-strings for string formatting

```python
def process_data(input_data: str) -> Dict[str, Any]:
    """
    Process input data and return results.

    Args:
        input_data: The input string to process

    Returns:
        Dict containing processed results
    """
    return {"result": f"Processed {input_data}"}
```

#### Documentation
* Use Markdown for documentation
* Follow Google Style Python Docstrings
* Keep line length reasonable
* Include code examples where appropriate

### Testing

* Write unit tests for new features
* Maintain test coverage above 80%
* Include integration tests where necessary
* Test edge cases
* Mock external dependencies

```python
def test_process_data():
    """Test data processing functionality."""
    input_data = "test"
    result = process_data(input_data)
    assert result["result"] == "Processed test"
```

### Ontology Development

1. **Adding New Concepts**
   ```turtle
   :NewConcept a owl:Class ;
       rdfs:label "New Concept" ;
       rdfs:comment "Description of the new concept" .
   ```

2. **Adding Properties**
   ```turtle
   :hasProperty a owl:ObjectProperty ;
       rdfs:domain :NewConcept ;
       rdfs:range :ExistingConcept ;
       rdfs:comment "Description of the property" .
   ```

3. **Validation**
   ```bash
   python tools/validate_ontology.py
   ```

### Documentation

* Update README.md if needed
* Add/update API documentation
* Include examples
* Update changelog
* Add migration guides for breaking changes

## Release Process

1. Version Bump
   ```bash
   bump2version patch  # or minor, or major
   ```

2. Update Changelog
   ```markdown
   ## [1.0.1] - 2024-01-26
   ### Added
   - New feature X
   ### Fixed
   - Bug in feature Y
   ```

3. Create Release
   ```bash
   git tag -a v1.0.1 -m "Release version 1.0.1"
   git push origin v1.0.1
   ```

## Additional Notes

### Issue and Pull Request Labels

* bug: Something isn't working
* enhancement: New feature or request
* documentation: Improvements or additions to documentation
* good first issue: Good for newcomers
* help wanted: Extra attention is needed
* invalid: This doesn't seem right
* question: Further information is requested
* wontfix: This will not be worked on

### Support

If you need help with your contribution:
1. Check the documentation
2. Ask in GitHub issues
3. Contact maintainers
4. Join our community channels

## Recognition

Contributors will be recognized in:
* README.md
* Release notes
* Contributors list
* Special mentions for significant contributions 