# Antiyoy Python Port

A Python port of the Antiyoy game with machine learning support.

## Setup

### Quick Setup

Run the setup script to create a virtual environment and install all dependencies:

```bash
./setup_dev_env.sh
```

This script will:
- Create a virtual environment in `.venv/`
- Install all dependencies from `requirements.txt`
- Verify the installation

### Manual Setup

If you prefer to set up manually:

1. Create a virtual environment:
```bash
python3 -m venv .venv
source .venv/bin/activate  # On Windows: .venv\Scripts\activate
```

2. Install dependencies:
```bash
pip install -r requirements.txt
```


## Web Interface


### Run the Web Server

Start the Flask development server:

```bash
cd antiyoy_py
source .venv/bin/activate
python web/app.py
```

### Run the server from a cached location - to enable continuous modification of source files.
```bash
./run_cached.sh
```

The web interface will be available at `http://localhost:5000`
And the visual test are available at `http://localhost:5000/unit_tests`


## Running Tests

### Run all tests:
```bash
cd antiyoy_py
source .venv/bin/activate
pytest tests/ -v
```

### Run a specific test method:
```bash
pytest tests/test_hex.py::TestHex::test_hex_initialization -v
```

### Run visual tests:
Visual tests can be run from the command line (they also work in the web UI):

```bash
# Run all visual tests
pytest tests/visual/ -v

# Run a specific visual test
pytest tests/visual/test_split_province.py::test_split_province_A -v
```

### Run tests with coverage:

Generate coverage report (terminal output):
```bash
cd antiyoy_py
source .venv/bin/activate
pytest tests/ --cov=core --cov=save_load --cov=players --cov=commands --cov=visibility --cov=ai --cov-report=term -v
```

Generate HTML coverage report:
```bash
pytest tests/ --cov=core --cov=save_load --cov=players --cov=commands --cov=visibility --cov=ai --cov-report=html -v
```

**Note:** The `tests/` path includes all tests, including visual tests in `tests/visual/`. Visual tests are automatically included when running the coverage command above.

## Project Structure

- `core/` - Core game logic (hexes, provinces, events, rulesets, game state)
- `campaign/` - Campaign level codes
- `save_load/` - Save/load system (encoder, decoder, format parser)
- `players/` - Player interfaces (base player, ML player, human player)
- `commands/` - Command system (types, validator, executor)
- `visibility/` - State view and fog-of-war filtering
- `ai/` - AI players (balancer variants)
- `tests/` - Unit tests


