# EdgeMindFlow

**EdgeMindFlow** (AgentNet-ComputerNet) — A network-intent-driven multi-agent edge task offloading system with low-latency self-optimization for smart campuses.

[![License](https://img.shields.io/badge/License-Apache%202.0-blue.svg)](LICENSE)

## Features

- **LATE Framework**: Three-tier offloading stack — LATE-Offload / LATE-Learn / LATE-RL
- **AgentNet Layer**: Natural-language intent → six-agent orchestration → closed-loop validation and self-healing
- **Digital Twin Smart Park**: Unified simulation of devices, network, and edge/cloud load
- **7 strategies × 4 scenarios**: 28 automated comparison experiments
- **Explainable Dashboard**: Task flow, topology highlights, strategy/scenario illustrations, ECharts metrics

## Architecture

```
Natural Language Intent
        ↓
AgentNet (Intent / Planner / Policy / Monitor / Validator / Recovery)
        ↓
Tool Layer → LATE Framework → Edge / Cloud Execution
        ↓
React Dashboard + SQLite Metrics
```

## Quick Start

### Requirements

- Python 3.10+
- Node.js 18+

### Install & Run

```bash
git clone https://github.com/SteveYang05/EdgeMindFlow.git
cd EdgeMindFlow

pip install -r requirements.txt
bash scripts/start_all.sh
```

| Service | URL |
|---------|-----|
| Dashboard | http://localhost:3000 |
| Edge API | http://localhost:8000/docs |
| Cloud API | http://localhost:8001/docs |

Stop services: `bash scripts/stop_all.sh`

### Conda (optional)

```bash
conda env create -f environment.yml
conda activate ComputerNet
bash scripts/start_all.sh
```

## Project Layout

```
backend/          Edge/Cloud services, offloading algorithms, AgentNet
frontend/         React + Vite + ECharts dashboard
simulator/        IoT device task simulation
ml/               LATE-Learn / LATE-RL training scripts
scripts/          Startup, experiments, tests
data/             Traces, pretrained weights, strategy/scenario illustrations
mqtt/             Optional MQTT broker
```

## Experiments & Testing

```bash
# 28 strategy×scenario runs (adjust duration as needed)
EXPERIMENT_DURATION_SEC=60 bash scripts/run_experiment.sh

# Export report
python scripts/export_report.py

# System test
bash scripts/test_system.sh

# Agent layer test
bash scripts/test_agent_layer.sh
```

## Optional LLM Agent

The default **rule_based** mode requires no API key. To enable LLM enhancement:

```bash
cp .env.example .env
# Set ENABLE_LLM_AGENT=1 and AGENT_LLM_API_KEY
bash scripts/stop_all.sh && bash scripts/start_all.sh
```

## Offloading Strategies

| Strategy | Description |
|----------|-------------|
| `local_only` | Execute all tasks locally |
| `cloud_only` | Offload all tasks to cloud |
| `edge_only` | Execute all tasks at edge |
| `static_rule` | Fixed task-type mapping |
| `dynamic` | **LATE-Offload** (proprietary; API name: `dynamic`) |
| `learned_late` | **LATE-Learn** Oracle-supervised learning |
| `late_rl` | **LATE-RL** reinforcement-learning enhancement |

## Experiment Scenarios

- `normal` — Baseline network
- `cloud_delay` — Degraded cloud link
- `edge_overload` — Edge overload
- `emergency` — Emergency alert

## Agent API Example

```bash
curl -X POST http://localhost:8000/api/agent/intent \
  -H 'Content-Type: application/json' \
  -d '{"intent_text":"When cloud link degrades, prioritize smoke alerts under 100ms latency","dry_run":true}'
```

## License

Apache License 2.0 — see [LICENSE](LICENSE).
