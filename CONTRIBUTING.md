# Contributing to InternTrack

Thank you for your interest in contributing to InternTrack! This document provides guidelines and instructions for contributing.

## Table of Contents

- [Code of Conduct](#code-of-conduct)
- [How to Contribute](#how-to-contribute)
- [Development Setup](#development-setup)
- [Coding Standards](#coding-standards)
- [Testing](#testing)
- [Pull Request Process](#pull-request-process)
- [Issue Guidelines](#issue-guidelines)

## Code of Conduct

Please be respectful and professional in all interactions. We are committed to providing a welcoming and inclusive experience for everyone.

## How to Contribute

### Reporting Bugs

1. Check existing issues to avoid duplicates
2. Create a new issue with the bug template
3. Include steps to reproduce, expected behavior, and actual behavior
4. Add relevant labels (bug, enhancement, etc.)

### Suggesting Features

1. Check existing feature requests
2. Create a new issue with the feature template
3. Describe the use case and benefits
4. Include mockups or examples if applicable

### Submitting Changes

1. Fork the repository
2. Create a feature branch: `git checkout -b feature/amazing-feature`
3. Make your changes
4. Run tests: `pytest`
5. Commit: `git commit -m 'feat: add amazing feature'`
6. Push: `git push origin feature/amazing-feature`
7. Open a Pull Request

## Development Setup

### Prerequisites

- Python 3.11+
- pip
- Git

### Setup Steps

```bash
# Clone repository
git clone https://github.com/partha442004/CyberGuide.git
cd CyberGuide

# Create virtual environment
python -m venv venv
source venv/bin/activate  # Linux/Mac
# or
venv\Scripts\activate  # Windows

# Install dependencies
pip install -r requirements.txt
pip install -r requirements-dev.txt

# Copy environment file
cp .env.example .env

# Run tests
pytest
```

## Coding Standards

### Python Style

- Follow PEP 8
- Use type hints for all functions
- Write docstrings for all public methods
- Keep functions under 50 lines when possible

### Naming Conventions

- **Variables**: `snake_case`
- **Functions**: `snake_case`
- **Classes**: `PascalCase`
- **Constants**: `UPPER_SNAKE_CASE`
- **Files**: `snake_case.py`

### Import Order

1. Standard library
2. Third-party packages
3. Local imports

### Example

```python
"""
Module docstring.
"""

import asyncio
from typing import Optional, List

from fastapi import APIRouter, Depends
from sqlalchemy.ext.asyncio import AsyncSession

from interntrack.domain.models import Job
from interntrack.services.job_service import JobService


class JobService:
    """Job service for managing job listings."""

    def __init__(self, session: AsyncSession):
        self.session = session

    async def get_job(self, job_id: str) -> Optional[Job]:
        """Get a job by ID.

        Args:
            job_id: The job identifier.

        Returns:
            The job if found, None otherwise.
        """
        # Implementation
        pass
```

## Testing

### Running Tests

```bash
# Run all tests
pytest

# Run with coverage
pytest --cov=interntrack

# Run specific test file
pytest tests/unit/test_job_service.py

# Run with verbose output
pytest -v
```

### Writing Tests

- Test both success and failure cases
- Use descriptive test names
- Mock external dependencies
- Aim for 80% coverage on new code

### Test Structure

```python
import pytest
from unittest.mock import AsyncMock

class TestJobService:
    """Tests for JobService."""

    @pytest.fixture
    def mock_session(self):
        """Mock database session."""
        return AsyncMock()

    @pytest.fixture
    def service(self, mock_session):
        """Create service with mocked dependencies."""
        return JobService(mock_session)

    @pytest.mark.asyncio
    async def test_get_job_success(self, service):
        """Test getting a job successfully."""
        # Arrange
        job_id = "test-123"
        
        # Act
        result = await service.get_job(job_id)
        
        # Assert
        assert result is not None
```

## Pull Request Process

### Before Submitting

1. Run all tests: `pytest`
2. Run linter: `ruff check .`
3. Run formatter: `ruff format .`
4. Update documentation if needed
5. Update CHANGELOG.md

### Releasing (version bump checklist)

When cutting a new release, keep the version single-source-of-truth in sync:

1. Add the new entry to `CHANGELOG.md` (e.g. `## [1.x.0] - YYYY-MM-DD`)
2. Bump `__version__` in `src/interntrack/__init__.py` **and**
   `src/cybershield/__init__.py` to the same value
3. Update `APP_VERSION` in `.env` and `.env.example`
4. Update the version canaries in `tests/unit/test_main.py`
   (`TestVersionConsistency.test_version_is_current_release`) and
   `src/cybershield/tests/test_version.py` so CI validates the new release
5. Sync hardcoded version strings in deployment artifacts:
   `dashboard/app.py` (About line), `k8s/helm/Chart.yaml`
   (`version`/`appVersion`), and `deploy/oracle-cloud/setup.sh`
   (`APP_VERSION=`)

### PR Template

```markdown
## Description
Brief description of changes

## Type of Change
- [ ] Bug fix
- [ ] New feature
- [ ] Breaking change
- [ ] Documentation update

## Testing
- [ ] Tests pass locally
- [ ] New tests added (if applicable)
- [ ] Coverage maintained/improved

## Checklist
- [ ] Code follows project style
- [ ] Self-review completed
- [ ] Documentation updated
- [ ] No breaking changes
```

### Review Process

1. PR will be reviewed by maintainers
2. Address feedback promptly
3. Make requested changes
4. PR will be merged after approval

## Issue Guidelines

### Bug Report Template

```markdown
**Describe the bug**
A clear description of the bug.

**To Reproduce**
Steps to reproduce the behavior.

**Expected behavior**
What you expected to happen.

**Screenshots**
If applicable, add screenshots.

**Environment**
- OS: [e.g., Windows 11]
- Python version: [e.g., 3.11.0]
```

### Feature Request Template

```markdown
**Is your feature request related to a problem?**
A clear description of the problem.

**Describe the solution**
Your proposed solution.

**Describe alternatives**
Alternative solutions considered.

**Additional context**
Any other context or screenshots.
```

## Questions?

Feel free to open an issue for any questions about contributing!
