#!/bin/bash

# Exit on error
set -e

echo "Setting up local development environment for Teams Bot..."

# Check OS and set package manager
if [[ "$OSTYPE" == "darwin"* ]]; then
    # macOS
    if ! command -v brew &> /dev/null; then
        echo "Installing Homebrew..."
        /bin/bash -c "$(curl -fsSL https://raw.githubusercontent.com/Homebrew/install/HEAD/install.sh)"
    fi
    
    echo "Installing dependencies with Homebrew..."
    brew install python@3.10 node npm azure-functions-core-tools@4 1password-cli
    brew install --cask bot-framework-emulator
elif [[ "$OSTYPE" == "linux-gnu"* ]]; then
    # Linux
    if command -v apt-get &> /dev/null; then
        echo "Installing dependencies with apt..."
        sudo apt-get update
        sudo apt-get install -y python3.10 python3.10-venv nodejs npm
        
        # Install Azure Functions Core Tools
        curl https://packages.microsoft.com/keys/microsoft.asc | gpg --dearmor > microsoft.gpg
        sudo mv microsoft.gpg /etc/apt/trusted.gpg.d/microsoft.gpg
        sudo sh -c 'echo "deb [arch=amd64] https://packages.microsoft.com/repos/microsoft-ubuntu-$(lsb_release -cs)-prod $(lsb_release -cs) main" > /etc/apt/sources.list.d/dotnetdev.list'
        sudo apt-get update
        sudo apt-get install -y azure-functions-core-tools-4
        
        # Install 1Password CLI
        curl -sS https://downloads.1password.com/linux/keys/1password.asc | sudo gpg --dearmor --output /usr/share/keyrings/1password-archive-keyring.gpg
        echo "deb [arch=amd64 signed-by=/usr/share/keyrings/1password-archive-keyring.gpg] https://downloads.1password.com/linux/debian/amd64 stable main" | sudo tee /etc/apt/sources.list.d/1password.list
        sudo apt-get update && sudo apt-get install -y 1password-cli
    else
        echo "Unsupported Linux distribution. Please install dependencies manually."
        exit 1
    fi
else
    echo "Unsupported operating system. Please install dependencies manually."
    exit 1
fi

# Install Miniconda if not present
if ! command -v conda &> /dev/null; then
    echo "Installing Miniconda..."
    if [[ "$OSTYPE" == "darwin"* ]]; then
        MINICONDA_URL="https://repo.anaconda.com/miniconda/Miniconda3-latest-MacOSX-x86_64.sh"
    else
        MINICONDA_URL="https://repo.anaconda.com/miniconda/Miniconda3-latest-Linux-x86_64.sh"
    fi
    
    curl -o miniconda.sh $MINICONDA_URL
    bash miniconda.sh -b -p $HOME/miniconda
    rm miniconda.sh
    
    # Initialize conda
    eval "$($HOME/miniconda/bin/conda shell.bash hook)"
    conda init
fi

# Create conda environment
echo "Creating conda environment..."
conda env create -f environment.yml

# Activate environment
echo "Activating conda environment..."
conda activate chatbot-llm

# Install development tools
echo "Installing development tools..."
pip install pytest pytest-cov black flake8 mypy

# Setup local configuration
echo "Setting up local configuration..."
if [ ! -f .env ]; then
    cp .env.template .env
    echo "Created .env file from template. Please update with your settings."
fi

if [ ! -f local.settings.json ]; then
    cat > local.settings.json << EOL
{
  "IsEncrypted": false,
  "Values": {
    "FUNCTIONS_WORKER_RUNTIME": "python",
    "AzureWebJobsStorage": "UseDevelopmentStorage=true",
    "FUNCTIONS_HTTPWORKER_PORT": "3978",
    "AZURE_FUNCTIONS_ENVIRONMENT": "Development"
  },
  "Host": {
    "LocalHttpPort": 3978,
    "CORS": "*"
  }
}
EOL
    echo "Created local.settings.json"
fi

# Create logs directory
mkdir -p logs

# Setup git hooks
echo "Setting up git hooks..."
if [ -d .git ]; then
    cat > .git/hooks/pre-commit << 'EOL'
#!/bin/bash

# Colors for output
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
NC='\033[0m' # No Color

echo -e "${YELLOW}Running pre-commit checks...${NC}"

# Initialize error flag
ERROR=0

# Function to run check and update error flag
run_check() {
    local cmd=$1
    local name=$2
    echo -e "\n${YELLOW}Running $name...${NC}"
    if ! $cmd; then
        echo -e "${RED}$name failed!${NC}"
        ERROR=1
    fi
}

# Get staged files by type
STAGED_PY_FILES=$(git diff --cached --name-only --diff-filter=d | grep ".py$" || true)
STAGED_TTL_FILES=$(git diff --cached --name-only --diff-filter=d | grep ".ttl$" || true)
STAGED_SESSION_FILES=$(git diff --cached --name-only --diff-filter=d | grep "session.ttl$" || true)

# Check for absolute paths in all staged files
echo -e "\n${YELLOW}Checking for absolute paths...${NC}"
ABSOLUTE_PATHS=$(git diff --cached | grep -E "file:///|/Users/|/home/" || true)
if [ ! -z "$ABSOLUTE_PATHS" ]; then
    echo -e "${RED}Error: Found absolute paths in changes!${NC}"
    echo "Please use relative paths. Found in:"
    echo "$ABSOLUTE_PATHS"
    ERROR=1
fi

# Check for secrets and sensitive data
echo -e "\n${YELLOW}Checking for sensitive data...${NC}"
if git diff --cached | grep -i "password\|secret\|key\|token" > /dev/null; then
    echo -e "${RED}Warning: Possible sensitive data detected in changes!${NC}"
    echo "Please review the following lines:"
    git diff --cached | grep -i "password\|secret\|key\|token"
    ERROR=1
fi

# Run Python checks if Python files are staged
if [ ! -z "$STAGED_PY_FILES" ]; then
    echo -e "\n${YELLOW}Running Python code quality checks...${NC}"
    
    # Format code with black
    run_check "python -m black --check $STAGED_PY_FILES" "black"
    
    # Sort imports
    run_check "python -m isort --check-only $STAGED_PY_FILES" "isort"
    
    # Run flake8
    run_check "python -m flake8 $STAGED_PY_FILES" "flake8"
    
    # Run mypy type checking
    run_check "python -m mypy $STAGED_PY_FILES" "mypy"
    
    # Run pylint
    run_check "python -m pylint $STAGED_PY_FILES" "pylint"
    
    # Run bandit security checks
    run_check "python -m bandit -r $STAGED_PY_FILES" "bandit"
    
    # Run critical tests
    echo -e "\n${YELLOW}Running critical tests...${NC}"
    if ! python -m pytest tools/tests/test_validate_local_env.py -v; then
        echo -e "${RED}Critical tests failed!${NC}"
        ERROR=1
    fi
fi

# Validate environment files if changed
ENV_FILES=$(git diff --cached --name-only --diff-filter=d | grep -E "\.env.*|environment\.yml" || true)
if [ ! -z "$ENV_FILES" ]; then
    echo -e "\n${YELLOW}Validating environment files...${NC}"
    if ! python tools/validate_local_env.py; then
        echo -e "${RED}Environment validation failed!${NC}"
        ERROR=1
    fi
fi

# Validate ontology files if changed
if [ ! -z "$STAGED_TTL_FILES" ]; then
    echo -e "\n${YELLOW}Validating ontology files...${NC}"
    
    # Run ontology validation
    if ! python tools/validate_ontology_state.py; then
        echo -e "${RED}Ontology validation failed!${NC}"
        ERROR=1
    fi
    
    # Additional RDF syntax validation
    if command -v riot &> /dev/null; then
        for file in $STAGED_TTL_FILES; do
            if ! riot --validate $file; then
                echo -e "${RED}RDF syntax validation failed for $file${NC}"
                ERROR=1
            fi
        done
    else
        echo -e "${YELLOW}Warning: riot command not found, skipping RDF syntax validation${NC}"
        echo "Install Apache Jena for additional RDF validation: https://jena.apache.org/"
    fi
fi

# Validate session and checkpoint if session.ttl changed
if [ ! -z "$STAGED_SESSION_FILES" ]; then
    echo -e "\n${YELLOW}Validating session and checkpoint state...${NC}"
    
    # Run checkpoint tests
    if ! python -m pytest tools/tests/test_get_checkpoint.py -v; then
        echo -e "${RED}Checkpoint validation failed!${NC}"
        ERROR=1
    fi
    
    # Check checkpoint output
    if ! python tools/get_checkpoint.py > /dev/null; then
        echo -e "${RED}Invalid checkpoint state!${NC}"
        ERROR=1
    else
        # Show checkpoint summary
        echo -e "\n${GREEN}Current checkpoint state:${NC}"
        python tools/get_checkpoint.py | head -n 10
    fi
fi

# Validate session state
echo "Validating session state..."
if ! python tools/validate_session_state.py; then
    echo "❌ Session state validation failed"
    echo "Please ensure session.ttl has valid checkpoint and prompt state"
    exit 1
fi

if [ $ERROR -ne 0 ]; then
    echo -e "\n${RED}Pre-commit checks failed! Please fix the issues and try again.${NC}"
    echo -e "To bypass these checks, use git commit --no-verify (not recommended)\n"
    exit 1
fi

echo -e "\n${GREEN}All pre-commit checks passed!${NC}"
exit 0
EOL
    chmod +x .git/hooks/pre-commit
    
    # Install additional dependencies for pre-commit checks
    pip install pylint bandit isort rdflib
    
    # Check for Apache Jena (riot command)
    if ! command -v riot &> /dev/null; then
        if [[ "$OSTYPE" == "darwin"* ]]; then
            echo "Installing Apache Jena via Homebrew..."
            brew install jena
        elif [[ "$OSTYPE" == "linux-gnu"* ]]; then
            echo "Please install Apache Jena manually:"
            echo "Visit: https://jena.apache.org/download/"
        fi
    fi
fi

# Verify installation
echo "Verifying installation..."
python tools/validate_local_env.py

echo "Local environment setup complete!"
echo "Next steps:"
echo "1. Update .env with your settings"
echo "2. Start the bot with: ./start-local.sh"
echo "3. Connect using Bot Framework Emulator: http://localhost:3978/api/messages" 