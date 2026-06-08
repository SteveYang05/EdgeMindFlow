#!/usr/bin/env bash
# AgentNet Layer 轻量测试 — 不跑 test_system.sh，不重跑正式实验
set -euo pipefail

ROOT="$(cd "$(dirname "$0")/.." && pwd)"
EDGE="${EDGE_URL:-http://localhost:8000}"
FRONT="${FRONTEND_URL:-http://localhost:3000}"
PASS=0
FAIL=0

ok() { echo "[PASS] $1"; PASS=$((PASS + 1)); }
fail() { echo "[FAIL] $1"; FAIL=$((FAIL + 1)); }

curl_json() {
  curl -sf "$@"
}

echo "=== AgentNet Layer Test ==="
echo "Edge: $EDGE"

# 1. status
if curl_json "$EDGE/api/agent/status" | grep -q '"agent_layer_enabled":true'; then
  ok "GET /api/agent/status"
else
  fail "GET /api/agent/status"
fi

# 2. examples
if curl_json "$EDGE/api/agent/examples" | grep -q '云端链路变差'; then
  ok "GET /api/agent/examples"
else
  fail "GET /api/agent/examples"
fi

# 3. plan
if curl_json -X POST "$EDGE/api/agent/plan" \
  -H 'Content-Type: application/json' \
  -d '{"intent_text":"云端链路变差时，优先保障烟雾告警任务在100ms内完成","dry_run":true}' \
  | grep -q '"plan_id"'; then
  ok "POST /api/agent/plan"
else
  fail "POST /api/agent/plan"
fi

# 4. intent dry_run
if curl_json -X POST "$EDGE/api/agent/intent" \
  -H 'Content-Type: application/json' \
  -d '{"intent_text":"当前系统是否满足低时延和高 QoS 要求？","dry_run":true,"auto_recover":false}' \
  | grep -q '"final_status":"dry_run"'; then
  ok "POST /api/agent/intent dry_run=true"
else
  fail "POST /api/agent/intent dry_run=true"
fi

# 5. intent execute simple switch
if curl_json -X POST "$EDGE/api/agent/intent" \
  -H 'Content-Type: application/json' \
  -d '{"intent_text":"进入紧急模式，优先保障门禁和烟雾告警","dry_run":false,"auto_recover":true}' \
  | grep -q '"final_status"'; then
  ok "POST /api/agent/intent dry_run=false"
else
  fail "POST /api/agent/intent dry_run=false"
fi

# 6. tools schema
if curl_json "$EDGE/api/agent/tools/schema" | grep -q '"set_scenario"'; then
  ok "GET /api/agent/tools/schema"
else
  fail "GET /api/agent/tools/schema"
fi

# 7. dashboard reachable
if curl -sf -o /dev/null "$FRONT" || curl -sf -o /dev/null "$FRONT/"; then
  ok "Dashboard reachable at $FRONT"
else
  fail "Dashboard reachable at $FRONT (is frontend running?)"
fi

echo ""
echo "=== Result: $PASS passed, $FAIL failed ==="
[ "$FAIL" -eq 0 ]
