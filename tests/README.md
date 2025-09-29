# Tests Directory

This directory contains all test files organized by category.

## Directory Structure

```
tests/
├── README.md                    # This file
├── integration/                 # Integration tests
├── proxy/                      # Proxy-related tests (moved from vpn_config/)
├── prompts/                    # Prompt implementation tests
└── [existing test files]       # Legacy test files (to be organized)
```

## Test Categories

### Integration Tests (`integration/`)
- End-to-end system tests
- Cross-component integration tests
- Database connectivity tests

### Proxy Tests (`proxy/`)
- Proxy server functionality tests
- Authentication and security tests
- Query processing tests
- Configuration tests

### Prompt Tests (`prompts/`)
- Prompt implementation validation tests
- Feature acceptance tests
- Configuration system tests

## Running Tests

### All Tests
```bash
python -m pytest tests/
```

### Specific Category
```bash
python -m pytest tests/proxy/          # Proxy tests
python -m pytest tests/integration/    # Integration tests
python -m pytest tests/prompts/        # Prompt tests
```

### Individual Test Files
```bash
python tests/proxy/test_proxy_auth.py
python tests/integration/test_complete_system.py
```

## Test Environment

Make sure to configure your environment variables before running tests:
```bash
cp .env.template .env
# Edit .env with your configuration
```

## Legacy Tests

The root `tests/` directory contains many legacy test files that were created during development. These should be gradually organized into the appropriate subdirectories or removed if obsolete.