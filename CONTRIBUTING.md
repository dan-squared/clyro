# Contributing to Clyro

Thank you for your interest in contributing to Clyro! We want to make contributing to this project as easy and transparent as possible.

## Developer Setup

1. **Clone the repository:**
   ```bash
   git clone https://github.com/dan-squared/clyro.git
   cd clyro
   ```

2. **Set up a Virtual Environment:**
   ```bash
   python -m venv venv
   # On Windows:
   venv\Scripts\activate
   # On macOS/Linux:
   source venv/bin/activate
   ```

3. **Install Dependencies:**
   ```bash
   pip install -r requirements.txt
   pip install -e .
   ```

## Development Workflow

### Coding Style & Linting
- This project uses **Ruff** for linting and code formatting.
- Ensure your code passes linting before submitting a PR:
  ```bash
  pip install ruff
  ruff check src/
  ruff format src/
  ```

### Running the App Locally
```bash
python -m clyro.main
```

### Testing
- We use `pytest` for testing. Run the test suite:
  ```bash
  pip install pytest
  pytest tests/
  ```

## Pull Request Process
1. Fork the repo and create your branch from `main`.
2. Make your changes, following the code style guidelines.
3. Ensure the CI pipeline passes (linting and tests).
4. Update the `README.md` if necessary to document new features or changes.
5. Submit your PR with a clear description of the problem it solves and your proposed solution.
