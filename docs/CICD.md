# CI/CD Setup for Celo MCP

This document describes the CI/CD setup for automatically publishing the `celo-mcp` package to PyPI using GitHub Actions.

## Overview

The CI/CD pipeline consists of two main workflows:

1. **Test Workflow** (`test.yml`) - Runs on every push and pull request
2. **Publish Workflow** (`publish.yml`) - Runs when a version tag is created

## Setup Instructions

### 1. PyPI Configuration

#### Option A: Trusted Publishing (Recommended)

1. Go to [PyPI](https://pypi.org) and log in to your account
2. Navigate to your project's settings (or create the project first)
3. Go to "Publishing" → "Add a new pending publisher"
4. Fill in the details:
   - **PyPI Project Name**: `celo-mcp`
   - **Owner**: `viral-sangani` (your GitHub username)
   - **Repository name**: `celo-mcp`
   - **Workflow name**: `publish.yml`
   - **Environment name**: (leave empty)

#### Option B: API Token (Alternative)

1. Generate an API token on PyPI
2. Add it as a GitHub secret named `PYPI_API_TOKEN`
3. Update the publish workflow to use the token instead of trusted publishing

### 2. GitHub Repository Setup

The workflows are already configured and will work automatically once you:

1. Push the workflow files to your repository
2. Set up PyPI trusted publishing (see above)

## Workflows

### Test Workflow

**File**: `.github/workflows/test.yml`

**Triggers**:

- Push to `main` or `develop` branches
- Pull requests to `main` or `develop` branches

**What it does**:

- Tests on Python 3.11 and 3.12
- Runs linting (ruff, black)
- Runs type checking (mypy)
- Runs tests (pytest)
- Tests package building and installation

### Publish Workflow

**File**: `.github/workflows/publish.yml`

**Triggers**:

- Push of tags matching `v*` (e.g., `v1.0.0`, `v0.2.1`)

**What it does**:

1. Runs all tests (same as test workflow)
2. Extracts version from the git tag
3. Updates `pyproject.toml` with the new version
4. Builds the package using `uv build`
5. Publishes to PyPI using trusted publishing
6. Creates a GitHub release with the built artifacts

## Creating a Release

### Method 1: Using the Release Script (Recommended)

Use the provided release script for easy version management:

```bash
# Check current version
python scripts/release.py current

# Create a patch release (0.1.0 → 0.1.1)
python scripts/release.py patch

# Create a minor release (0.1.0 → 0.2.0)
python scripts/release.py minor

# Create a major release (0.1.0 → 1.0.0)
python scripts/release.py major

# Create a custom version
python scripts/release.py custom --version 1.2.3

# Dry run to see what would happen
python scripts/release.py patch --dry-run
```

The script will:

1. Update the version in `pyproject.toml`
2. Commit the change
3. Create and push a git tag
4. Trigger the GitHub Actions workflow

### Method 2: Manual Release

```bash
# 1. Update version in pyproject.toml
# Edit the version field manually

# 2. Commit the change
git add pyproject.toml
git commit -m "Bump version to 0.1.1"

# 3. Create and push tag
git tag -a v0.1.1 -m "Release 0.1.1"
git push origin v0.1.1
git push
```

## Version Management

- Follow [Semantic Versioning](https://semver.org/): `MAJOR.MINOR.PATCH`
- **PATCH**: Bug fixes and small improvements
- **MINOR**: New features that are backward compatible
- **MAJOR**: Breaking changes

## Monitoring Releases

1. **GitHub Actions**: Check the "Actions" tab in your repository to monitor workflow runs
2. **PyPI**: Check [pypi.org/project/celo-mcp](https://pypi.org/project/celo-mcp) to verify the package was published
3. **GitHub Releases**: Check the "Releases" section of your repository

## Testing the Published Package

After a successful release, test the package:

```bash
# Install from PyPI
uvx install celo-mcp

# Test that it works
uvx celo-mcp --help

# Or install in a fresh environment
pip install celo-mcp
python -c "import celo_mcp; print('Success!')"
```

## Troubleshooting

### Common Issues

1. **PyPI Trusted Publishing Not Working**

   - Verify the publisher configuration matches exactly
   - Check that the workflow name is correct (`publish.yml`)
   - Ensure the repository and owner names are correct

2. **Tests Failing**

   - Check the test workflow logs in GitHub Actions
   - Run tests locally: `uv run pytest`
   - Fix any linting issues: `uv run ruff check . && uv run black --check .`

3. **Version Conflicts**

   - Ensure the version in `pyproject.toml` matches the git tag
   - PyPI doesn't allow re-uploading the same version

4. **Build Failures**
   - Test building locally: `uv build`
   - Check that all dependencies are properly specified

### Getting Help

- Check GitHub Actions logs for detailed error messages
- Review PyPI project settings
- Ensure all required files are committed to the repository

## Security Notes

- The workflows use trusted publishing, which is more secure than API tokens
- No secrets need to be stored in the repository
- The `id-token: write` permission is required for trusted publishing
- Only tagged releases trigger publishing, preventing accidental deployments
