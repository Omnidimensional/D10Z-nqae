# Contributing to Pyraclaw Universal Nodal Architecture

Thank you for your interest in contributing to the Pyraclaw project! This document provides guidelines and instructions for contributing.

## Table of Contents

- [Code of Conduct](#code-of-conduct)
- [Getting Started](#getting-started)
- [Development Process](#development-process)
- [Submitting Changes](#submitting-changes)
- [Style Guidelines](#style-guidelines)
- [Testing](#testing)
- [Documentation](#documentation)

## Code of Conduct

This project adheres to the Creative Commons Attribution-NonCommercial 4.0 International license. By participating, you are expected to uphold this code. Please report unacceptable behavior to the project maintainers.

## Getting Started

### Prerequisites

- Python 3.10 or higher
- Git
- A GitHub account

### Setting Up Development Environment

1. **Fork the repository**

   Click the "Fork" button on the GitHub repository page.

2. **Clone your fork**

   ```bash
   git clone https://github.com/YOUR-USERNAME/pyraclaw-nqae.git
   cd pyraclaw-nqae
   ```

3. **Add upstream remote**

   ```bash
   git remote add upstream https://github.com/pyraclaw-institute/pyraclaw-nqae.git
   ```

4. **Create a virtual environment**

   ```bash
   python -m venv venv
   source venv/bin/activate  # On Windows: venv\Scripts\activate
   ```

5. **Install dependencies**

   ```bash
   pip install -r requirements.txt
   pip install -e .[dev]
   ```

## Development Process

### 1. Sync with upstream

```bash
git fetch upstream
git checkout main
git merge upstream/main
```

### 2. Create a feature branch

```bash
git checkout -b feature/your-feature-name
```

### 3. Make your changes

Follow the style guidelines below and ensure all tests pass.

### 4. Commit your changes

```bash
git add .
git commit -m "Description of your changes"
```

### 5. Push to your fork

```bash
git push origin feature/your-feature-name
```

### 6. Submit a Pull Request

Go to the GitHub repository and click "New Pull Request".

## Submitting Changes

### Pull Request Guidelines

- **Describe your changes clearly** in the PR description
- **Reference any related issues** using GitHub keywords (fixes, closes, resolves)
- **Include tests** for new functionality
- **Update documentation** as needed
- **Ensure all CI checks pass** before requesting review

### Commit Message Format

```
type(scope): description

body (optional)

footer (optional)
```

Types:
- `feat`: New feature
- `fix`: Bug fix
- `docs`: Documentation changes
- `refactor`: Code refactoring
- `test`: Adding tests
- `chore`: Maintenance tasks

## Style Guidelines

### Python Code Style

We use the following tools for code quality:

- **Black**: Code formatting (line length: 100)
- **isort**: Import sorting
- **flake8**: Linting
- **mypy**: Type checking

### Formatting Commands

```bash
# Format code
black src/ tests/
isort src/ tests/

# Check formatting
black --check src/ tests/
isort --check-only src/ tests/
flake8 src/ tests/ --max-line-length=100

# Type checking
mypy src/ --ignore-missing-imports
```

### Code Style Rules

- Follow PEP 8 guidelines
- Use type hints for all functions
- Maximum line length: 100 characters
- Use descriptive variable and function names
- Write docstrings for all public functions and classes

### Docstring Format

```python
def function_name(param1: Type1, param2: Type2) -> ReturnType:
    """
    Brief description of the function.
    
    Args:
        param1: Description of param1
        param2: Description of param2
        
    Returns:
        Description of return value
        
    Example:
        >>> function_name(value1, value2)
        result
    """
```

## Testing

### Running Tests

```bash
# Run all tests
pytest tests/ -v

# Run with coverage
pytest tests/ --cov=src/ --cov-report=html

# Run specific test file
pytest tests/test_core.py -v

# Run specific test
pytest tests/test_core.py::TestCoherenceAnalyzer::test_compute_phi_clean_signal -v
```

### Writing Tests

- Place tests in the `tests/` directory
- Use pytest framework
- Follow the naming convention: `test_*.py`
- Group related tests in classes
- Use descriptive test names

### Test Coverage Requirements

- New code should have at least 80% test coverage
- Critical functions require 100% coverage

## Documentation

### Types of Documentation

1. **Code Documentation**: Docstrings in Python files
2. **API Documentation**: Generated with Sphinx
3. **User Guides**: Markdown files in `docs/`
4. **Examples**: Runnable scripts in `examples/`

### Building Documentation

```bash
pip install sphinx sphinx-rtd-theme
sphinx-build -b html docs/ docs/_build/
```

### Writing Documentation

- Use clear, concise language
- Include code examples where appropriate
- Explain *why*, not just *how*
- Keep documentation up to date with code changes

## Additional Notes

### Intellectual Property

- All contributions are subject to the CC BY-NC 4.0 license
- Commercial use requires explicit authorization
- All patent rights are reserved by the Byron Callaghan / Pyraclaw

### Questions?

- Check existing issues and documentation
- Open a new issue for questions
- Contact: contact@pyraclaw.institute

---

**Thank you for contributing to Pyraclaw!**
