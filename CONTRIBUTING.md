# Contributing to AWS Health MCP Server

Thank you for your interest in contributing! This document provides guidelines for contributing to the project.

## Development Setup

1. **Fork and clone the repository**
   ```bash
   git clone https://github.com/your-username/aws-health-mcp-server.git
   cd aws-health-mcp-server
   ```

2. **Create a virtual environment**
   ```bash
   python -m venv venv
   source venv/bin/activate  # On Windows: venv\Scripts\activate
   ```

3. **Install development dependencies**
   ```bash
   pip install -e ".[dev]"
   ```

## Development Workflow

1. **Create a feature branch**
   ```bash
   git checkout -b feature/your-feature-name
   ```

2. **Make your changes**
   - Follow the existing code style
   - Add tests for new functionality
   - Update documentation as needed

3. **Run tests and linting**
   ```bash
   # Format code
   black aws_health_mcp/
   isort aws_health_mcp/
   
   # Type checking
   mypy aws_health_mcp/
   
   # Run tests
   pytest tests/
   ```

4. **Commit your changes**
   ```bash
   git add .
   git commit -m "feat: add your feature description"
   ```

5. **Push and create a pull request**
   ```bash
   git push origin feature/your-feature-name
   ```

## Code Style

- Use [Black](https://black.readthedocs.io/) for code formatting
- Use [isort](https://pycqa.github.io/isort/) for import sorting
- Follow [PEP 8](https://pep8.org/) style guidelines
- Add type hints using [mypy](https://mypy.readthedocs.io/)

## Testing

- Write tests for all new functionality
- Ensure existing tests pass
- Aim for good test coverage
- Use pytest for testing

## Documentation

- Update README.md for user-facing changes
- Add docstrings to new functions and classes
- Update configuration examples if needed

## Pull Request Guidelines

- Provide a clear description of the changes
- Reference any related issues
- Ensure all CI checks pass
- Keep pull requests focused and atomic

## Reporting Issues

- Use the GitHub issue tracker
- Provide clear reproduction steps
- Include relevant system information
- Use appropriate issue labels

## Code of Conduct

Please be respectful and inclusive in all interactions. We follow the [Contributor Covenant](CODE_OF_CONDUCT.md).

## Questions?

Feel free to open an issue for questions or reach out to the maintainers.
