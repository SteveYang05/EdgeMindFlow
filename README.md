# EdgeMindFlow

**EdgeMindFlow**（AgentNet-ComputerNet）— 面向智能园区的网络意图驱动多智能体协同边缘任务卸载与低时延自优化系统。

[![License](https://img.shields.io/badge/License-Apache%202.0-blue.svg)](LICENSE)

## 特性

- **LATE Framework**：LATE-Offload / LATE-Learn / LATE-RL 三层卸载体系
- **AgentNet Layer**：自然语言意图 → 六智能体协同 → 闭环验证与自愈
- **Digital Twin Smart Park**：设备、网络、边缘/云端负载统一仿真
- **7 策略 × 4 场景**：28 组自动化对比实验
- **Explainable Dashboard**：任务流、拓扑高亮、策略/场景配图、ECharts 指标

## 架构概览

```
Natural Language Intent
        ↓
AgentNet (Intent / Planner / Policy / Monitor / Validator / Recovery)
        ↓
Tool Layer → LATE Framework → Edge / Cloud Execution
        ↓
React Dashboard + SQLite Metrics
```

## 快速开始

### 环境

- Python 3.10+
- Node.js 18+

### 安装与运行

```bash
git clone https://github.com/SteveYang05/EdgeMindFlow.git
cd EdgeMindFlow

pip install -r requirements.txt
bash scripts/start_all.sh
```

| 服务 | 地址 |
|------|------|
| Dashboard | http://localhost:3000 |
| Edge API | http://localhost:8000/docs |
| Cloud API | http://localhost:8001/docs |

停止：`bash scripts/stop_all.sh`

### Conda（可选）

```bash
conda env create -f environment.yml
conda activate ComputerNet
bash scripts/start_all.sh
```

## 目录结构

```
backend/          Edge/Cloud 服务、卸载算法、AgentNet
frontend/         React + Vite + ECharts Dashboard
simulator/        IoT 设备任务模拟
ml/               LATE-Learn / LATE-RL 训练脚本
scripts/          启动、实验、测试
data/             trace、预训练权重、策略/场景配图
mqtt/             可选 MQTT Broker
```

## 实验与测试

```bash
# 28 组策略×场景实验（可调时长）
EXPERIMENT_DURATION_SEC=60 bash scripts/run_experiment.sh

# 导出报告
python scripts/export_report.py

# 系统测试
bash scripts/test_system.sh

# Agent 层测试
bash scripts/test_agent_layer.sh
```

## 可选 LLM Agent

默认 **rule_based** 模式无需 API Key。启用 LLM 增强：

```bash
cp .env.example .env
# 设置 ENABLE_LLM_AGENT=1 与 AGENT_LLM_API_KEY
bash scripts/stop_all.sh && bash scripts/start_all.sh
```

## 卸载策略

| 策略 | 说明 |
|------|------|
| `local_only` | 全部本地执行 |
| `cloud_only` | 全部上云 |
| `edge_only` | 全部边缘 |
| `static_rule` | 固定规则映射 |
| `dynamic` | **LATE-Offload**（自研，API 名 dynamic） |
| `learned_late` | **LATE-Learn** Oracle 监督学习 |
| `late_rl` | **LATE-RL** 强化学习增强 |

## 实验场景

- `normal` — 基线网络
- `cloud_delay` — 云链路劣化
- `edge_overload` — 边缘过载
- `emergency` — 紧急告警

## Agent API 示例

```bash
curl -X POST http://localhost:8000/api/agent/intent \
  -H 'Content-Type: application/json' \
  -d '{"intent_text":"云端链路变差时，优先保障烟雾告警低时延","dry_run":true}'
```

## License

Apache License 2.0 — 见 [LICENSE](LICENSE)。
