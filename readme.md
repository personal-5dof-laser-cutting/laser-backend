# Laser Backend

## Project Setup

This project uses [uv](https://github.com/astral-sh/uv) for dependency management and [ruff](https://docs.astral.sh/ruff/) for linting and formatting.

### 1. Install uv

If you don't have `uv` installed, you can install it with:

```sh
curl -Ls https://astral.sh/uv/install.sh | sh
```

Or follow the instructions in the [uv documentation](https://github.com/astral-sh/uv#installation).

### 2. Initial setup

```sh
uv sync --group dev && uv run pre-commit install && cp .env.example .env
```

### 3. Run the project
```sh
uvicorn src.main:app --reload
```
### Docs will be available under http://127.0.0.1:8000/docs

## Using Ruff

[Ruff](https://docs.astral.sh/ruff/) is used for linting and formatting Python code. Ruff will automatically run pre-commit. To run manually, use: 

- check code style:

  ```sh
  ruff check
  ```

- automatically fix issues:

  ```sh
  ruff check --fix
  ```

- format code:

  ```sh
  ruff format 
  ```

## Development
### Tests
[Pytest](https://docs.pytest.org/) is used for testing. Run all tests with
```sh 
pytest
```