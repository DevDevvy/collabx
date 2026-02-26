# Contributing to CollabX

Thank you for your interest in contributing to CollabX! This document provides guidelines and instructions for contributing.

## Development Setup

1. **Clone the repository**

   ```bash
   git clone https://github.com/yourusername/collabx_cloud.git
   cd collabx_cloud
   ```

2. **Create a virtual environment**

   ```bash
   python -m venv .venv
   source .venv/bin/activate  # On Windows: .venv\Scripts\activate
   ```

3. **Install in development mode**
   ```bash
   pip install -U pip
   pip install -e ".[dev]"
   ```

## Code Style

We use [Ruff](https://github.com/astral-sh/ruff) for linting and formatting:

```bash
# Check for issues
ruff check src/ tests/

# Auto-fix issues
ruff check --fix src/ tests/

# Format code
ruff format src/ tests/
```

## Testing

Run the test suite before submitting changes:

```bash
# Run all tests
pytest

# Run with coverage
pytest --cov=src --cov-report=term-missing --cov-report=html

# Run specific tests
pytest tests/test_integration.py -v

# Run tests matching a pattern
pytest -k "test_export"
```

## Making Changes

1. **Create a new branch**

   ```bash
   git checkout -b feature/your-feature-name
   ```

2. **Make your changes**
   - Write clear, concise code
   - Add tests for new functionality
   - Update documentation as needed
   - Follow existing code patterns

3. **Test your changes**

   ```bash
   pytest
   ruff check src/ tests/
   ```

4. **Commit your changes**

   ```bash
   git add .
   git commit -m "Add feature: description of your changes"
   ```

5. **Push and create a pull request**
   ```bash
   git push origin feature/your-feature-name
   ```

## Pull Request Guidelines

- **Title**: Clear, descriptive title summarizing the change
- **Description**: Explain what changed and why
- **Tests**: Include tests for new features or bug fixes
- **Documentation**: Update README.md or add inline documentation as needed
- **Changelog**: Add an entry to CHANGELOG.md under "Unreleased"

## Project Structure

```
collabx_cloud/
├── src/
│   ├── collabx/           # CLI application
│   │   ├── main.py        # CLI commands
│   │   ├── state.py       # State management
│   │   ├── stream.py      # Log streaming
│   │   ├── deploy/        # Deployment utilities
│   │   └── providers/     # Cloud provider implementations
│   └── collabx_server/    # FastAPI server
│       ├── main.py        # Server application
│       ├── storage.py     # Database operations
│       ├── security.py    # Security utilities
│       ├── settings.py    # Configuration
│       ├── middleware.py  # Middleware components
│       └── export.py      # Export functionality
├── tests/                 # Test suite
├── README.md             # User documentation
├── CHANGELOG.md          # Version history
└── pyproject.toml        # Project configuration
```

## Adding New Features

When adding new features:

1. **Design**: Consider the user experience and API design
2. **Implementation**: Write clean, testable code
3. **Tests**: Add comprehensive tests
4. **Documentation**: Update README.md with usage examples
5. **Changelog**: Add entry to CHANGELOG.md

## Reporting Issues

When reporting issues, please include:

- CollabX version (`pip show collabx`)
- Python version (`python --version`)
- Operating system
- Steps to reproduce
- Expected vs. actual behavior
- Relevant logs or error messages

## Code of Conduct

- Be respectful and inclusive
- Focus on constructive feedback
- Help others learn and grow
- Keep discussions on-topic

## Questions?

Feel free to open an issue for questions about contributing!

## License

By contributing to CollabX, you agree that your contributions will be licensed under the MIT License.
