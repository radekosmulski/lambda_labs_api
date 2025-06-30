# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## Project Overview

Lambda Labs API Client - A Python package providing CLI and library interfaces for managing GPU instances on Lambda Labs Cloud. Key features include listing instances, browsing GPU types, launching instances, terminating instances, and auto-retry for high-demand GPUs. The CLI uses Rich for enhanced terminal output with progress bars, colored output, and interactive prompts.

## Development Commands

```bash
# Install for development
pip install -e .[dev]

# Run tests (Note: No tests currently exist in the project)
pytest

# Format code
black lambda_labs_client/ --line-length 100

# Lint code
flake8 lambda_labs_client/

# Type check
mypy lambda_labs_client/

# Build package
python -m build

# Clean build artifacts
rm -rf build/ dist/ *.egg-info/
```

## Architecture

The package follows a single-file architecture where all functionality resides in `client.py`:

- `lambda_labs_client/` - Main package directory
  - `client.py` - Contains both `LambdaLabsClient` class and CLI implementation (604 lines)
  - `cli.py` - Minimal wrapper (6 lines) that imports and calls `main()` from client.py
  - `__init__.py` - Exports `LambdaLabsClient` and defines package metadata

Key architectural decisions:
- Single `LambdaLabsClient` class encapsulates all API operations
- CLI is implemented within client.py using argparse, with cli.py serving as the entry point
- Auto-retry mechanism with configurable intervals for high-demand GPU instances
- Uses Bearer token authentication via `LAMBDA_API_KEY` environment variable
- All methods return parsed JSON responses or raise exceptions with descriptive error messages

## Important Implementation Details

1. **API Integration**: 
   - Base URL: `https://cloud.lambda.ai/api/v1`
   - Key endpoints:
     - `GET /instances` - List running instances
     - `GET /instance-types` - Get available GPU types with regions and availability
     - `POST /instance-operations/launch` - Launch instances with configuration
     - `POST /instance-operations/terminate` - Terminate specific instances
     - `GET /ssh-keys` - List available SSH keys
   - Full OpenAPI spec: Available locally at `lambda_labs_openapi.json` (v1.7.0)

2. **Core Methods**:
   - `list_instances()` - Returns list of running instances with details
   - `get_instance_types()` - Returns GPU types with pricing and availability
   - `launch_instance()` - Launches instance with specified configuration
   - `terminate_instance()` - Terminates single instance by ID
   - `terminate_instances()` - Batch terminate multiple instances
   - `terminate_all_instances()` - Terminate all running instances
   - `check_instance_availability_silent()` - Check availability without output

3. **CLI Features**:
   - Pretty-printed tables for instance and GPU type listings
   - Filtering options for GPU types (--available, --unavailable, --gpu-type)
   - Auto-retry mechanism with customizable check interval
   - Interactive termination with confirmation prompts
   - Graceful handling of Ctrl+C during retry loops

4. **Error Handling**: 
   - Custom error messages for common scenarios (auth failures, capacity issues)
   - Structured error responses with error codes when available
   - Fallback to HTTP status codes when API doesn't provide detailed errors

5. **Code Standards**:
   - Type hints throughout with strict mypy configuration
   - Black formatter with 100-character line length
   - Flake8 linting with exceptions for E501 and W503

## API Reference

- **OpenAPI Specification**: The complete Lambda Labs API v1.7.0 OpenAPI specification is stored at `lambda_labs_openapi.json`. This file contains:
  - All available API endpoints (including unimplemented ones like filesystems)
  - Request/response schemas with detailed type information
  - Error response formats and codes
  - Authentication requirements
  
  Use this spec when:
  - Adding new API endpoints to the client
  - Understanding request parameter requirements
  - Debugging API response issues
  - Checking for API updates or new features