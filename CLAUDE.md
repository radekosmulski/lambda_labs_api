# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## Project Overview

Lambda Labs API Client - A Python package providing CLI and library interfaces for managing GPU instances on Lambda Labs Cloud. Key features include listing instances, browsing GPU types, launching instances, and auto-retry for high-demand GPUs.

## Development Commands

```bash
# Install for development
pip install -e .[dev]

# Run tests
pytest

# Format code
black lambda_labs_client/ --line-length 100

# Lint code
flake8 lambda_labs_client/

# Type check
mypy lambda_labs_client/

# Build package
python -m build
```

## Architecture

The package structure:
- `lambda_labs_client/` - Main package directory
  - `client.py` - Core `LambdaLabsClient` class with API operations
  - `cli.py` - CLI entry point and command implementations
  - `__init__.py` - Exports `LambdaLabsClient`
- `lambda_labs_client.py` - Duplicate of client.py (exists in root for backward compatibility)

Key architectural decisions:
- Single class `LambdaLabsClient` handles all API interactions
- CLI built on top of the client class for separation of concerns
- Auto-retry mechanism implemented for high-demand GPU instances
- Uses Bearer token authentication stored in `LAMBDA_API_KEY` environment variable

## Important Implementation Details

1. **API Endpoints**: The client interacts with Lambda Labs API v1:
   - `/instances` - List running instances
   - `/instance-types` - Get available GPU types
   - `/instance-operations/launch` - Launch instances
   - `/instance-operations/terminate` - Terminate instances
   - `/ssh-keys` - List SSH keys
   - Full API specification available at: https://cloud.lambda.ai/api/v1/openapi.json

2. **Error Handling**: The client provides user-friendly error messages for common issues like authentication failures, insufficient capacity, and network errors.

3. **Type Safety**: The codebase uses type hints throughout and is configured for strict mypy checking.

4. **Code Style**: Black formatter with 100-character line length, follows PEP 8 conventions. Flake8 is configured in `.flake8` file to match the line length.