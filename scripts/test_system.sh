#!/bin/bash
# ComputerNet system test
set -e

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
PROJECT_ROOT="$(dirname "$SCRIPT_DIR")"
EDGE_URL="${EDGE_URL:-http://localhost:8000}"
CLOUD_URL="${CLOUD_URL:-http://localhost:8001}"

PASS=0
FAIL=0

# Ensure ML dependencies available (LATE-Learn)
python -m pip install -q scikit-learn joblib 2>/dev/null || true

check() {
    local name=$1 url=$2 expected=$3
    echo -n "[Test] $name ... "
    resp=$(curl -s -o /dev/null -w "%{http_code}" "$url" 2>/dev/null || echo "000")
    if [ "$resp" = "$expected" ]; then echo "PASS"; PASS=$((PASS+1))
    else echo "FAIL (HTTP $resp)"; FAIL=$((FAIL+1)); fi
}

echo "=========================================="
echo " ComputerNet system test"
echo "=========================================="

check "Cloud Health" "$CLOUD_URL/api/health" "200"
check "Edge Health" "$EDGE_URL/api/health" "200"
check "Metrics" "$EDGE_URL/api/metrics" "200"
check "Metrics scope=recent_100" "$EDGE_URL/api/metrics?scope=recent_100" "200"
check "Tasks recent 100" "$EDGE_URL/api/tasks/recent?limit=100" "200"
check "Topology" "$EDGE_URL/api/topology" "200"
check "Experiments" "$EDGE_URL/api/experiments/summary" "200"

echo -n "[Test] Metrics includes data_scope ... "
if curl -s "$EDGE_URL/api/metrics?scope=recent_100" | grep -q "data_scope"; then echo "PASS"; PASS=$((PASS+1))
else echo "FAIL"; FAIL=$((FAIL+1)); fi

echo -n "[Test] Submit smoke_alert ... "
curl -s -X POST "$EDGE_URL/api/tasks/submit" -H "Content-Type: application/json" \
  -d '{"task_id":"test_p3_smoke","device_id":"smoke_sensor_01","task_type":"smoke_alert","priority":"high","data_size_kb":5,"compute_cost":0.4,"deadline_ms":300,"timestamp":"2026-05-22T12:00:00Z","topic":"smart_park/devices/smoke_sensor_01/tasks"}' | grep -q decision \
  && echo "PASS" && PASS=$((PASS+1)) || { echo "FAIL"; FAIL=$((FAIL+1)); }

echo -n "[Test] security/critical alerts ... "
sleep 1
ALERTS=$(curl -s "$EDGE_URL/api/alerts?limit=5")
echo "$ALERTS" | grep -q "security" && echo "$ALERTS" | grep -q "critical" \
  && echo "PASS" && PASS=$((PASS+1)) || { echo "FAIL"; FAIL=$((FAIL+1)); }

echo -n "[Test] alert_category field ... "
echo "$ALERTS" | grep -q "alert_category" && echo "PASS" && PASS=$((PASS+1)) || { echo "FAIL"; FAIL=$((FAIL+1)); }

curl -s -X POST "$EDGE_URL/api/scenario/normal" > /dev/null
curl -s -X POST "$EDGE_URL/api/strategy/dynamic" > /dev/null
check "Scenario normal" "$EDGE_URL/api/scenario" "200"

echo -n "[Test] POST /api/strategy/local_only ... "
curl -s -X POST "$EDGE_URL/api/strategy/local_only" | grep -q "local_only" \
  && echo "PASS" && PASS=$((PASS+1)) || { echo "FAIL"; FAIL=$((FAIL+1)); }

echo -n "[Test] POST /api/strategy/static_rule ... "
curl -s -X POST "$EDGE_URL/api/strategy/static_rule" | grep -q "static_rule" \
  && echo "PASS" && PASS=$((PASS+1)) || { echo "FAIL"; FAIL=$((FAIL+1)); }

echo -n "[Test] static_rule: smoke_alert → edge ... "
curl -s -X POST "$EDGE_URL/api/strategy/static_rule" > /dev/null
R=$(curl -s -X POST "$EDGE_URL/api/tasks/submit" -H "Content-Type: application/json" \
  -d '{"task_id":"test_sr_smoke","device_id":"smoke_sensor_01","task_type":"smoke_alert","priority":"high","data_size_kb":5,"compute_cost":0.4,"deadline_ms":300,"timestamp":"2026-05-22T12:00:00Z","topic":"smart_park/devices/smoke_sensor_01/tasks"}')
echo "$R" | grep -q '"decision":"edge"' && echo "PASS" && PASS=$((PASS+1)) || { echo "FAIL ($R)"; FAIL=$((FAIL+1)); }

echo -n "[Test] static_rule: temperature_report → local ... "
curl -s -X POST "$EDGE_URL/api/strategy/static_rule" > /dev/null
R=$(curl -s -X POST "$EDGE_URL/api/tasks/submit" -H "Content-Type: application/json" \
  -d '{"task_id":"test_sr_temp","device_id":"temp_sensor_01","task_type":"temperature_report","priority":"low","data_size_kb":2,"compute_cost":0.1,"deadline_ms":5000,"timestamp":"2026-05-22T12:00:00Z","topic":"smart_park/devices/temp_sensor_01/tasks"}')
echo "$R" | grep -q '"decision":"local"' && echo "PASS" && PASS=$((PASS+1)) || { echo "FAIL ($R)"; FAIL=$((FAIL+1)); }

echo -n "[Test] static_rule: image_detection → edge ... "
curl -s -X POST "$EDGE_URL/api/strategy/static_rule" > /dev/null
R=$(curl -s -X POST "$EDGE_URL/api/tasks/submit" -H "Content-Type: application/json" \
  -d '{"task_id":"test_sr_img","device_id":"camera_01","task_type":"image_detection","priority":"high","data_size_kb":512,"compute_cost":0.8,"deadline_ms":500,"timestamp":"2026-05-22T12:00:00Z","topic":"smart_park/devices/camera_01/tasks"}')
echo "$R" | grep -q '"decision":"edge"' && echo "PASS" && PASS=$((PASS+1)) || { echo "FAIL ($R)"; FAIL=$((FAIL+1)); }

curl -s -X POST "$EDGE_URL/api/strategy/dynamic" > /dev/null

echo -n "[Test] Demo trigger_smoke ... "
curl -s -X POST "$EDGE_URL/api/demo/trigger_smoke" | grep -q "status" \
  && echo "PASS" && PASS=$((PASS+1)) || { echo "FAIL"; FAIL=$((FAIL+1)); }

echo -n "[Test] reset_demo_data.sh ... "
export PYTHONPATH="$PROJECT_ROOT"
bash "$PROJECT_ROOT/scripts/reset_demo_data.sh" > /dev/null 2>&1 \
  && echo "PASS" && PASS=$((PASS+1)) || { echo "FAIL"; FAIL=$((FAIL+1)); }

echo -n "[Test] prepare_demo QUICK ... "
PREPARE_QUICK=1 DEMO_EXPERIMENT_DURATION_SEC=3 python "$PROJECT_ROOT/scripts/prepare_demo.py" > /dev/null 2>&1 \
  && echo "PASS" && PASS=$((PASS+1)) || { echo "FAIL"; FAIL=$((FAIL+1)); }

[ -f "$PROJECT_ROOT/results/experiment_summary.csv" ] && echo "[Test] CSV exists ... PASS" && PASS=$((PASS+1)) || { echo "[Test] CSV exists ... FAIL"; FAIL=$((FAIL+1)); }

echo -n "[Test] run_experiment QUICK (5 strategies) ... "
EXPERIMENT_QUICK=1 EXPERIMENT_DURATION_SEC=2 python "$PROJECT_ROOT/scripts/run_experiment.py" > /dev/null 2>&1 \
  && echo "PASS" && PASS=$((PASS+1)) || { echo "FAIL"; FAIL=$((FAIL+1)); }

echo -n "[Test] export_report.py (5 strategies) ... "
python "$PROJECT_ROOT/scripts/export_report.py" > /dev/null 2>&1 && [ -f "$PROJECT_ROOT/results/report.md" ] \
  && grep -q "static_rule" "$PROJECT_ROOT/results/report.md" \
  && grep -q "local_only" "$PROJECT_ROOT/results/report.md" \
  && echo "PASS" && PASS=$((PASS+1)) || { echo "FAIL"; FAIL=$((FAIL+1)); }

echo -n "[Test] Metrics includes qos_satisfaction_rate ... "
curl -s "$EDGE_URL/api/metrics?scope=recent_100" | grep -q "qos_satisfaction_rate" \
  && echo "PASS" && PASS=$((PASS+1)) || { echo "FAIL"; FAIL=$((FAIL+1)); }

echo -n "[Test] LATE-Offload: smoke_alert reason ... "
curl -s -X POST "$EDGE_URL/api/scenario/normal" > /dev/null
curl -s -X POST "$EDGE_URL/api/strategy/dynamic" > /dev/null
R=$(curl -s -X POST "$EDGE_URL/api/tasks/submit" -H "Content-Type: application/json" \
  -d '{"task_id":"test_late_smoke","device_id":"smoke_sensor_01","task_type":"smoke_alert","priority":"high","data_size_kb":5,"compute_cost":0.4,"deadline_ms":300,"timestamp":"2026-05-22T12:00:00Z","topic":"smart_park/devices/smoke_sensor_01/tasks"}')
echo "$R" | grep -qiE "LATE-Offload|safety-critical" \
  && echo "PASS" && PASS=$((PASS+1)) || { echo "FAIL ($R)"; FAIL=$((FAIL+1)); }

echo -n "[Test] LATE-Offload: temperature_report decision ... "
R=$(curl -s -X POST "$EDGE_URL/api/tasks/submit" -H "Content-Type: application/json" \
  -d '{"task_id":"test_late_temp","device_id":"temp_sensor_01","task_type":"temperature_report","priority":"low","data_size_kb":2,"compute_cost":0.1,"deadline_ms":5000,"timestamp":"2026-05-22T12:00:00Z","topic":"smart_park/devices/temp_sensor_01/tasks"}')
echo "$R" | grep -qE '"decision":"(local|edge|cloud)"' \
  && echo "PASS" && PASS=$((PASS+1)) || { echo "FAIL ($R)"; FAIL=$((FAIL+1)); }

echo -n "[Test] experiment includes qos_satisfaction_rate ... "
grep -q "qos_satisfaction_rate" "$PROJECT_ROOT/results/experiment_summary.json" 2>/dev/null \
  && echo "PASS" && PASS=$((PASS+1)) || { echo "FAIL"; FAIL=$((FAIL+1)); }

echo -n "[Test] report.md includes LATE-Offload ... "
python "$PROJECT_ROOT/scripts/export_report.py" > /dev/null 2>&1 \
  && grep -q "LATE-Offload" "$PROJECT_ROOT/results/report.md" \
  && echo "PASS" && PASS=$((PASS+1)) || { echo "FAIL"; FAIL=$((FAIL+1)); }

# Key file checks
for f in presentation/ppt_outline.md presentation/demo_script.md presentation/qa.md \
         docs/figures/system_architecture.mmd docs/figures/task_flow.mmd \
         docs/figures/late_offload_method.mmd; do
  [ -f "$PROJECT_ROOT/$f" ] && echo "[Test] $f exists ... PASS" && PASS=$((PASS+1)) || { echo "[Test] $f exists ... FAIL"; FAIL=$((FAIL+1)); }
done

echo -n "[Test] Frontend :3000 ... "
FE=$(curl -s -o /dev/null -w "%{http_code}" "http://localhost:3000" 2>/dev/null || echo "000")
[ "$FE" = "200" ] && echo "PASS" && PASS=$((PASS+1)) || echo "SKIP ($FE)"

echo -n "[Test] GET /api/datasets ... "
# Restart services so Edge process loads scikit-learn (LATE-Learn)
bash "$SCRIPT_DIR/stop_all.sh" > /dev/null 2>&1 || true
sleep 1
bash "$SCRIPT_DIR/start_all.sh" > /dev/null 2>&1
sleep 8
curl -s "$EDGE_URL/api/datasets" | grep -q "mec_edge" \
  && curl -s "$EDGE_URL/api/datasets" | grep -q "google_cluster" \
  && echo "PASS" && PASS=$((PASS+1)) || { echo "FAIL"; FAIL=$((FAIL+1)); }

echo -n "[Test] POST /api/datasets/download (MEC+EUA) ... "
curl -s -X POST "$EDGE_URL/api/datasets/download" | grep -q "mec_edge" \
  && echo "PASS" && PASS=$((PASS+1)) || { echo "FAIL"; FAIL=$((FAIL+1)); }

echo -n "[Test] google_cluster manual_only ... "
GC=$(curl -s -o /dev/null -w "%{http_code}" -X POST "$EDGE_URL/api/datasets/download/google_cluster")
[ "$GC" = "400" ] && echo "PASS" && PASS=$((PASS+1)) || { echo "FAIL (HTTP $GC)"; FAIL=$((FAIL+1)); }

echo -n "[Test] train_late_learn.py oracle (CPU) ... "
python -m pip install -q scikit-learn joblib > /dev/null 2>&1
LATE_LEARN_LABEL_SOURCE=oracle LATE_LEARN_TRAIN_LIMIT=1000 python "$PROJECT_ROOT/scripts/train_late_learn.py" > /dev/null 2>&1 \
  && [ -f "$PROJECT_ROOT/data/models/late_learn.pkl" ] \
  && echo "PASS" && PASS=$((PASS+1)) || { echo "FAIL"; FAIL=$((FAIL+1)); }

echo -n "[Test] model_metadata label_source=oracle ... "
grep -q '"label_source": "oracle"' "$PROJECT_ROOT/ml/models/model_metadata.json" 2>/dev/null \
  && echo "PASS" && PASS=$((PASS+1)) || { echo "FAIL"; FAIL=$((FAIL+1)); }

echo -n "[Test] evaluation_report oracle_agreement ... "
grep -q 'oracle_agreement' "$PROJECT_ROOT/ml/models/evaluation_report.json" 2>/dev/null \
  && echo "PASS" && PASS=$((PASS+1)) || { echo "FAIL"; FAIL=$((FAIL+1)); }

echo -n "[Test] evaluation_report avg_regret ... "
grep -q 'avg_regret' "$PROJECT_ROOT/ml/models/evaluation_report.json" 2>/dev/null \
  && echo "PASS" && PASS=$((PASS+1)) || { echo "FAIL"; FAIL=$((FAIL+1)); }

echo -n "[Test] GET /api/ml/status label_source ... "
curl -s "$EDGE_URL/api/ml/status" | grep -q 'label_source' \
  && echo "PASS" && PASS=$((PASS+1)) || { echo "FAIL"; FAIL=$((FAIL+1)); }

echo -n "[Test] POST /api/strategy/learned_late ... "
curl -s -X POST "$EDGE_URL/api/strategy/learned_late" | grep -q "learned_late" \
  && echo "PASS" && PASS=$((PASS+1)) || { echo "FAIL"; FAIL=$((FAIL+1)); }

echo -n "[Test] LATE-Learn: smoke_alert reason ... "
curl -s -X POST "$EDGE_URL/api/strategy/learned_late" > /dev/null
curl -s -X POST "$EDGE_URL/api/ml/train?limit=800" > /dev/null 2>&1
R=$(curl -s -X POST "$EDGE_URL/api/tasks/submit" -H "Content-Type: application/json" \
  -d '{"task_id":"test_learn_smoke","device_id":"smoke_sensor_01","task_type":"smoke_alert","priority":"high","data_size_kb":5,"compute_cost":0.4,"deadline_ms":300,"timestamp":"2026-05-22T12:00:00Z","topic":"smart_park/devices/smoke_sensor_01/tasks"}')
echo "$R" | grep -qE '"decision":"(local|edge|cloud)"' \
  && echo "PASS" && PASS=$((PASS+1)) || { echo "FAIL ($R)"; FAIL=$((FAIL+1)); }

echo -n "[Test] ablation_late_learn.py small sample ... "
LATE_LEARN_ABLATION_SAMPLES=1000 LATE_LEARN_TRAIN_LIMIT=1000 python "$PROJECT_ROOT/ml/ablation_late_learn.py" > /dev/null 2>&1 \
  && [ -f "$PROJECT_ROOT/results/late_learn_ablation.csv" ] \
  && echo "PASS" && PASS=$((PASS+1)) || { echo "FAIL"; FAIL=$((FAIL+1)); }

echo -n "[Test] export_report Oracle/Regret section ... "
python "$PROJECT_ROOT/scripts/export_report.py" > /dev/null 2>&1 \
  && grep -qE "Oracle Labeling|Regret Evaluation" "$PROJECT_ROOT/results/report.md" \
  && echo "PASS" && PASS=$((PASS+1)) || { echo "FAIL"; FAIL=$((FAIL+1)); }

curl -s -X POST "$EDGE_URL/api/strategy/dynamic" > /dev/null

[ -f "$PROJECT_ROOT/docs/datasets.md" ] && echo "[Test] docs/datasets.md exists ... PASS" && PASS=$((PASS+1)) || { echo "[Test] docs/datasets.md exists ... FAIL"; FAIL=$((FAIL+1)); }

echo -n "[Test] train_late_rl.sh small sample ... "
RL_TRAIN_EPISODES=3 RL_EPISODE_LENGTH=20 bash "$PROJECT_ROOT/scripts/train_late_rl.sh" > /dev/null 2>&1 \
  && [ -f "$PROJECT_ROOT/data/models/late_rl.pkl" ] \
  && curl -s -X POST "$EDGE_URL/api/rl/reload" > /dev/null \
  && echo "PASS" && PASS=$((PASS+1)) || { echo "FAIL"; FAIL=$((FAIL+1)); }

echo -n "[Test] GET /api/rl/status ... "
curl -s "$EDGE_URL/api/rl/status" | grep -q 'fallback_enabled' \
  && echo "PASS" && PASS=$((PASS+1)) || { echo "FAIL"; FAIL=$((FAIL+1)); }

echo -n "[Test] POST /api/rl/reload ... "
curl -s -X POST "$EDGE_URL/api/rl/reload" | grep -q 'status' \
  && echo "PASS" && PASS=$((PASS+1)) || { echo "FAIL"; FAIL=$((FAIL+1)); }

echo -n "[Test] POST /api/strategy/late_rl ... "
curl -s -X POST "$EDGE_URL/api/strategy/late_rl" | grep -q "late_rl" \
  && echo "PASS" && PASS=$((PASS+1)) || { echo "FAIL"; FAIL=$((FAIL+1)); }

echo -n "[Test] late_rl smoke_alert decision ... "
curl -s -X POST "$EDGE_URL/api/strategy/late_rl" > /dev/null
R=$(curl -s -X POST "$EDGE_URL/api/tasks/submit" -H "Content-Type: application/json" \
  -d '{"task_id":"test_rl_smoke","device_id":"smoke_sensor_01","task_type":"smoke_alert","priority":"high","data_size_kb":5,"compute_cost":0.4,"deadline_ms":300,"timestamp":"2026-05-22T12:00:00Z","topic":"smart_park/devices/smoke_sensor_01/tasks"}')
echo "$R" | grep -qE '"decision":"(local|edge|cloud)"' \
  && echo "$R" | grep -qiE "LATE-RL|fallback" \
  && echo "PASS" && PASS=$((PASS+1)) || { echo "FAIL ($R)"; FAIL=$((FAIL+1)); }

echo -n "[Test] GET /api/digital_twin/status ... "
DT=$(curl -s "$EDGE_URL/api/digital_twin/status")
echo "$DT" | grep -q 'device_twin' && echo "$DT" | grep -q 'network_twin' \
  && echo "$DT" | grep -q 'edge_twin' && echo "$DT" | grep -q 'cloud_twin' \
  && echo "$DT" | grep -q 'workload_twin' \
  && echo "PASS" && PASS=$((PASS+1)) || { echo "FAIL"; FAIL=$((FAIL+1)); }

echo -n "[Test] export_report LATE-RL ... "
python "$PROJECT_ROOT/scripts/export_report.py" > /dev/null 2>&1 \
  && grep -q "LATE-RL" "$PROJECT_ROOT/results/report.md" \
  && echo "PASS" && PASS=$((PASS+1)) || { echo "FAIL"; FAIL=$((FAIL+1)); }

curl -s -X POST "$EDGE_URL/api/strategy/dynamic" > /dev/null

echo -n "[Test] RL candidate sweep script ... "
[ -f "$PROJECT_ROOT/scripts/sweep_late_rl.py" ] \
  && [ -f "$PROJECT_ROOT/scripts/sweep_late_rl.sh" ] \
  && [ -f "$PROJECT_ROOT/scripts/evaluate_rl_candidates.py" ] \
  && [ -f "$PROJECT_ROOT/scripts/promote_rl_candidate.sh" ] \
  && [ -d "$PROJECT_ROOT/data/models/rl_candidates" ] \
  && python "$PROJECT_ROOT/scripts/sweep_late_rl.py" --dry-run > /dev/null 2>&1 \
  && echo "PASS" && PASS=$((PASS+1)) || { echo "FAIL"; FAIL=$((FAIL+1)); }

echo ""
echo "=========================================="
echo " Result: $PASS passed, $FAIL failed"
echo "=========================================="
exit $FAIL
