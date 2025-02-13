# Snowflake Cortex Teams Bot

A Microsoft Teams bot integration for Snowflake Cortex, enabling seamless data analytics and collaboration within Teams channels.

## Documentation

📚 [View the full documentation index](docs/index.md) for comprehensive guides, references, and examples.

## Overview and Purpose

The Snowflake Cortex Teams Bot is designed to bridge the gap between Microsoft Teams collaboration and Snowflake's data analytics capabilities. This integration allows teams to:

- Query Snowflake data directly from Teams channels
- Receive automated alerts and insights
- Share and collaborate on data analytics
- Manage data access and permissions seamlessly

## Directory Structure

```
.
├── teams-bot/              # Main bot application
│   ├── bot/               # Core bot logic
│   ├── handlers/          # Message and event handlers
│   └── middleware/        # Bot middleware components
├── tools/                 # Development and utility scripts
├── tests/                 # Test suite
├── docs/                  # Documentation
└── ontologies/           # RDF/OWL ontologies for bot knowledge
```

## Setup Instructions

### Prerequisites

- Python 3.8 or higher
- Conda package manager
- Microsoft Teams development account
- Snowflake account with appropriate permissions

### Environment Setup

1. Create the conda environment:
```bash
conda env create -f environment.yml
conda activate chatbot-llm
```

2. Configure environment variables:
```bash
cp .env.example .env
# Edit .env with your credentials
```

3. Register the bot in Microsoft Teams:
   - Follow the [Microsoft Teams Bot Registration Guide](https://docs.microsoft.com/en-us/microsoftteams/platform/bots/how-to/create-a-bot-for-teams)
   - Add the bot credentials to your `.env` file

### Development Setup

1. Install development dependencies:
```bash
conda install -n chatbot-llm --file requirements-dev.txt
```

2. Set up pre-commit hooks:
```bash
pre-commit install
```

## Development Workflow

1. **Branch Management**
   - Main branch: `main` - production-ready code
   - Development branch: `develop` - integration branch
   - Feature branches: `feature/*` - new features
   - Hotfix branches: `hotfix/*` - urgent fixes

2. **Development Process**
   - Create a feature branch from `develop`
   - Implement changes with tests
   - Submit PR for review
   - Merge to `develop` after approval

3. **Testing**
```bash
# Run unit tests
pytest tests/unit

# Run integration tests
pytest tests/integration

# Run all tests with coverage
pytest --cov=teams-bot tests/
```

## Contribution Guidelines

1. **Code Style**
   - Follow PEP 8 guidelines
   - Use type hints
   - Document functions and classes
   - Keep functions focused and small

2. **Pull Request Process**
   - Create descriptive PR titles
   - Fill out the PR template
   - Include test coverage
   - Link related issues

3. **Commit Messages**
   - Use conventional commits format
   - Reference issues where applicable
   - Keep commits focused and atomic

4. **Documentation**
   - Update README for major changes
   - Document new features
   - Keep API documentation current

## Ontology Integration

The bot uses RDF/OWL ontologies for knowledge representation:

```turtle
@prefix bot: <./chatbot#> .
@prefix snow: <./snowflake#> .
@prefix teams: <./teams#> .

bot:TeamsBot a owl:Class ;
    rdfs:label "Teams Bot" ;
    rdfs:comment "Main bot application class" .
```

## License

This project is licensed under the MIT License - see the [LICENSE](LICENSE) file for details.

## Support

For support and questions:
- Create an issue in the repository
- Contact the development team
- Check the [documentation](docs/)
