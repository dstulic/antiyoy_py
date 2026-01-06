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

## Running Tests

### Run all tests:
```bash
.venv/bin/pytest tests/ -v
```

Or if the virtual environment is activated:
```bash
pytest tests/ -v
```

### Continuous Integration

Tests are automatically run on GitHub Actions for:
- Python 3.10, 3.11, and 3.12
- On push to main/master/develop branches
- On pull requests
- Can be manually triggered via workflow_dispatch

See `.github/workflows/tests.yml` for the CI configuration.

### Run a specific test file:
```bash
pytest tests/test_hex.py -v
```

### Run a specific test class:
```bash
pytest tests/test_hex.py::TestHex -v
```

### Run a specific test method:
```bash
pytest tests/test_hex.py::TestHex::test_hex_initialization -v
```

### Run tests with coverage:

First, install the coverage plugin:
```bash
pip install pytest-cov
```

Generate coverage report (terminal output):
```bash
pytest tests/ --cov=core --cov=save_load --cov=players --cov=commands --cov=visibility --cov=ai --cov-report=term -v
```

Generate HTML coverage report:
```bash
pytest tests/ --cov=core --cov=save_load --cov=players --cov=commands --cov=visibility --cov=ai --cov-report=html -v
```

**View the HTML coverage report:**
After running the command above, open the generated HTML report in your browser:
```bash
# On Linux/Mac:
open htmlcov/index.html
# Or:
xdg-open htmlcov/index.html

# On Windows:
start htmlcov/index.html
```

The HTML report provides an interactive view showing:
- Overall coverage percentage per module
- Line-by-line coverage highlighting (green=covered, red=not covered)
- File-by-file breakdown
- Missing line indicators

You can also combine both terminal and HTML reports:
```bash
pytest tests/ --cov=core --cov=save_load --cov=players --cov=commands --cov=visibility --cov=ai --cov-report=term --cov-report=html -v
```

### Run tests and show print statements:
```bash
pytest tests/ -v -s
```

### Run tests in parallel (faster):
```bash
pip install pytest-xdist
pytest tests/ -n auto
```

### To run tests with coverage report:
```bash
pytest tests/ --cov=core --cov=save_load --cov=players --cov=commands --cov=visibility --cov=ai --cov-report=term -v
```

## Project Structure

- `core/` - Core game logic (hexes, provinces, events, rulesets, game state)
- `campaign/` - Campaign level codes
- `save_load/` - Save/load system (encoder, decoder, format parser)
- `players/` - Player interfaces (base player, ML player, human player)
- `commands/` - Command system (types, validator, executor)
- `visibility/` - State view and fog-of-war filtering
- `ai/` - AI players (random, balancer variants)
- `tests/` - Unit tests

## Usage Examples

### Decode a campaign level:
```python
from save_load.decoder import GameStateDecoder
from campaign.levels import get_level_code

decoder = GameStateDecoder()
level_code = get_level_code(1)
game_state, campaign_index = decoder.decode(level_code)
print(f"Decoded level with {len(game_state.hexes)} hexes")
```

### Encode a game state:
```python
from save_load.encoder import GameStateEncoder

encoder = GameStateEncoder()
encoded = encoder.encode(game_state, campaign_level_index=1)
print(f"Encoded to {len(encoded)} characters")
```

## Web Interface

### Setup Assets

Before running the web interface, set up the game assets:

```bash
cd antiyoy_py/web
python setup_assets.py
```

This will create a symlink (or copy on Windows) from the original game assets to the web static directory.

### Run the Web Server

Start the Flask development server:

```bash
cd antiyoy_py
.venv/bin/python web/app.py
```

Or if the virtual environment is activated:

```bash
python web/app.py
```

The web interface will be available at `http://localhost:5000`

### Web Interface Features

- **Landing Page**: Main menu with campaign button
- **Campaign Selector**: Browse and select available campaign levels
- **Game Screen**: Play campaign levels with:
  - Hamburger menu (top left) with options:
    - Restart: Restart the current level
    - Save: Save game progress
    - Exit: Return to main menu
  - Game board (rendering to be implemented)
