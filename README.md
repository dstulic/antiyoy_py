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

## ML Training

Train a reinforcement learning agent to play Antiyoy using [Stable-Baselines3](https://stable-baselines3.readthedocs.io/) with action masking.

### Quick Start

```bash
source .venv/bin/activate
python -m ml.train
```

This trains a MaskablePPO agent on levels 0 and 1 for 1M timesteps with campaign-default opponent difficulty.

### Options

```bash
python -m ml.train \
    --algo MaskablePPO \      # MaskablePPO or MaskableA2C
    --timesteps 1000000 \     # total environment steps
    --levels 0 1 5 \          # specific levels to train on
    --level-range 0 10 \      # or an inclusive range (overrides --levels)
    --difficulty campaign \    # campaign (default) | easy | average | hard | expert | balancer
    --n-envs 4 \              # parallel game environments
    --lr 0.0003 \             # learning rate
    --max-turns 500 \         # turns before episode truncation
    --shaping-weight 0.1 \    # reward shaping weight for ownership changes
    --log-dir ml_logs \       # evaluation logs
    --model-dir ml_models     # checkpoint and final model output
```

`--difficulty campaign` (the default) automatically uses the level-appropriate difficulty from the campaign progression (Easy for levels 0-11, Average for 12-23, Hard for 24-59, etc.).

### Monitoring

Training logs are written to `ml_tb_logs/`. View them with TensorBoard:

```bash
tensorboard --logdir ml_tb_logs
```

### Output

- Checkpoints: `ml_models/antiyoy_*.zip`
- Best model (by evaluation reward): `ml_models/best/best_model.zip`
- Final model: `ml_models/antiyoy_final.zip`

## Project Structure

- `core/` - Core game logic (hexes, provinces, events, rulesets, game state)
- `campaign/` - Campaign level codes
- `save_load/` - Save/load system (encoder, decoder, format parser)
- `players/` - Player interfaces (base player, ML player, human player)
- `commands/` - Command system (types, validator, executor)
- `visibility/` - State view and fog-of-war filtering
- `ai/` - AI players (balancer variants)
- `ml/` - ML training and inference (Gymnasium env, observation encoder, action mapper, reward, training script)
- `tests/` - Unit tests


