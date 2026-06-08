"""SQLite 数据库 - 任务记录、告警、实验结果持久化。"""
import shutil
import sqlite3
from datetime import datetime
from pathlib import Path
from typing import Any, Dict, List, Optional

from backend.common.config import BACKUPS_DIR, DB_PATH


def _get_conn():
    conn = sqlite3.connect(str(DB_PATH), check_same_thread=False)
    conn.row_factory = sqlite3.Row
    return conn


def _column_exists(conn, table: str, column: str) -> bool:
    rows = conn.execute(f"PRAGMA table_info({table})").fetchall()
    return any(r["name"] == column for r in rows)


def _migrate_db(conn):
    """旧库缺少新字段时做增量迁移。"""
    if not _column_exists(conn, "alerts", "alert_category"):
        conn.execute("ALTER TABLE alerts ADD COLUMN alert_category TEXT DEFAULT 'system'")
    if not _column_exists(conn, "alerts", "alert_level"):
        conn.execute("ALTER TABLE alerts ADD COLUMN alert_level TEXT DEFAULT 'info'")
    if not _column_exists(conn, "alerts", "alert_type"):
        conn.execute("ALTER TABLE alerts ADD COLUMN alert_type TEXT DEFAULT 'system_event'")
    if not _column_exists(conn, "tasks", "data_size_kb"):
        conn.execute("ALTER TABLE tasks ADD COLUMN data_size_kb REAL DEFAULT 0")
    if not _column_exists(conn, "tasks", "experiment_id"):
        conn.execute("ALTER TABLE tasks ADD COLUMN experiment_id TEXT DEFAULT ''")
    if not _column_exists(conn, "experiment_results", "qos_satisfaction_rate"):
        conn.execute(
            "ALTER TABLE experiment_results ADD COLUMN qos_satisfaction_rate REAL DEFAULT 0"
        )


def init_db():
    """初始化数据库表。"""
    with _get_conn() as conn:
        conn.executescript("""
            CREATE TABLE IF NOT EXISTS tasks (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                task_id TEXT UNIQUE,
                device_id TEXT,
                task_type TEXT,
                priority TEXT,
                decision TEXT,
                reason TEXT,
                execution_location TEXT,
                total_latency_ms REAL,
                upload_latency_ms REAL,
                queue_latency_ms REAL,
                compute_latency_ms REAL,
                return_latency_ms REAL,
                deadline_ms REAL,
                deadline_met INTEGER,
                success INTEGER,
                edge_score REAL,
                cloud_score REAL,
                local_score REAL,
                scenario TEXT,
                strategy TEXT,
                data_size_kb REAL DEFAULT 0,
                experiment_id TEXT DEFAULT '',
                timestamp TEXT,
                created_at TEXT DEFAULT CURRENT_TIMESTAMP
            );
            CREATE TABLE IF NOT EXISTS alerts (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                task_id TEXT,
                device_id TEXT,
                message TEXT,
                level TEXT,
                alert_category TEXT DEFAULT 'system',
                alert_level TEXT DEFAULT 'info',
                alert_type TEXT DEFAULT 'system_event',
                timestamp TEXT,
                created_at TEXT DEFAULT CURRENT_TIMESTAMP
            );
            CREATE TABLE IF NOT EXISTS strategy_stats (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                strategy TEXT,
                avg_latency_ms REAL,
                p95_latency_ms REAL,
                success_rate REAL,
                deadline_violation_rate REAL,
                emergency_avg_latency_ms REAL,
                edge_task_count INTEGER,
                cloud_task_count INTEGER,
                local_task_count INTEGER,
                updated_at TEXT
            );
            CREATE TABLE IF NOT EXISTS experiment_results (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                experiment_id TEXT,
                scenario TEXT,
                strategy TEXT,
                duration_sec REAL,
                total_tasks INTEGER,
                avg_latency_ms REAL,
                p95_latency_ms REAL,
                urgent_avg_latency_ms REAL,
                deadline_violation_rate REAL,
                success_rate REAL,
                local_task_count INTEGER,
                edge_task_count INTEGER,
                cloud_task_count INTEGER,
                cloud_bandwidth_kb REAL,
                edge_cpu_percent REAL,
                cloud_cpu_percent REAL,
                alert_count INTEGER,
                qos_satisfaction_rate REAL DEFAULT 0,
                timestamp TEXT,
                created_at TEXT DEFAULT CURRENT_TIMESTAMP
            );
        """)
        _migrate_db(conn)
        conn.commit()


def insert_task(result: Dict[str, Any]) -> None:
    """插入任务执行结果。"""
    with _get_conn() as conn:
        conn.execute(
            """INSERT OR REPLACE INTO tasks (
                task_id, device_id, task_type, priority, decision, reason,
                execution_location, total_latency_ms, upload_latency_ms,
                queue_latency_ms, compute_latency_ms, return_latency_ms,
                deadline_ms, deadline_met, success, edge_score, cloud_score,
                local_score, scenario, strategy, data_size_kb, experiment_id, timestamp
            ) VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?)""",
            (
                result.get("task_id"),
                result.get("device_id"),
                result.get("task_type"),
                result.get("priority"),
                result.get("decision"),
                result.get("reason"),
                result.get("execution_location"),
                result.get("total_latency_ms"),
                result.get("upload_latency_ms"),
                result.get("queue_latency_ms"),
                result.get("compute_latency_ms"),
                result.get("return_latency_ms"),
                result.get("deadline_ms"),
                1 if result.get("deadline_met") else 0,
                1 if result.get("success") else 0,
                result.get("edge_score"),
                result.get("cloud_score"),
                result.get("local_score"),
                result.get("scenario"),
                result.get("strategy"),
                result.get("data_size_kb", 0),
                result.get("experiment_id", ""),
                result.get("timestamp"),
            ),
        )
        conn.commit()


def insert_alert(
    task_id: str,
    device_id: str,
    message: str,
    alert_category: str = "system",
    alert_level: str = "info",
    alert_type: str = "system_event",
    level: str = None,
) -> None:
    """插入分类告警记录。"""
    # 兼容旧 level 字段
    legacy_level = level or alert_level
    with _get_conn() as conn:
        conn.execute(
            """INSERT INTO alerts (
                task_id, device_id, message, level,
                alert_category, alert_level, alert_type, timestamp
            ) VALUES (?,?,?,?,?,?,?,?)""",
            (
                task_id,
                device_id,
                message,
                legacy_level,
                alert_category,
                alert_level,
                alert_type,
                datetime.utcnow().isoformat(),
            ),
        )
        conn.commit()


def _normalize_alert(row: Dict[str, Any]) -> Dict[str, Any]:
    """兼容旧 alerts 数据。"""
    d = dict(row)
    if not d.get("alert_category"):
        d["alert_category"] = "system"
    if not d.get("alert_level"):
        d["alert_level"] = d.get("level", "info")
    if not d.get("alert_type"):
        d["alert_type"] = "system_event"
    return d


def get_recent_tasks(limit: int = 50) -> List[Dict[str, Any]]:
    with _get_conn() as conn:
        rows = conn.execute(
            "SELECT * FROM tasks ORDER BY id DESC LIMIT ?", (limit,)
        ).fetchall()
    return [dict(r) for r in rows]


def get_all_tasks(limit: int = 200) -> List[Dict[str, Any]]:
    return get_recent_tasks(limit)


def get_alerts(limit: int = 30, category: str = None) -> List[Dict[str, Any]]:
    with _get_conn() as conn:
        if category:
            rows = conn.execute(
                """SELECT * FROM alerts WHERE alert_category=?
                   ORDER BY id DESC LIMIT ?""",
                (category, limit),
            ).fetchall()
        else:
            rows = conn.execute(
                "SELECT * FROM alerts ORDER BY id DESC LIMIT ?", (limit,)
            ).fetchall()
    return [_normalize_alert(dict(r)) for r in rows]


def get_alert_counts() -> Dict[str, int]:
    with _get_conn() as conn:
        total = conn.execute("SELECT COUNT(*) as c FROM alerts").fetchone()["c"]
        security = conn.execute(
            "SELECT COUNT(*) as c FROM alerts WHERE alert_category='security'"
        ).fetchone()["c"]
        performance = conn.execute(
            "SELECT COUNT(*) as c FROM alerts WHERE alert_category='performance'"
        ).fetchone()["c"]
        system = conn.execute(
            "SELECT COUNT(*) as c FROM alerts WHERE alert_category='system'"
        ).fetchone()["c"]
    return {
        "alert_count": total,
        "security_alert_count": security,
        "performance_warning_count": performance,
        "system_event_count": system,
    }


def get_task_latencies(limit: int = 500) -> List[float]:
    with _get_conn() as conn:
        rows = conn.execute(
            "SELECT total_latency_ms FROM tasks ORDER BY id DESC LIMIT ?", (limit,)
        ).fetchall()
    return [r["total_latency_ms"] for r in rows if r["total_latency_ms"] is not None]


def count_by_location(since_id: int = 0) -> Dict[str, int]:
    with _get_conn() as conn:
        if since_id > 0:
            rows = conn.execute(
                """SELECT execution_location, COUNT(*) as cnt FROM tasks
                   WHERE id > ? GROUP BY execution_location""",
                (since_id,),
            ).fetchall()
        else:
            rows = conn.execute(
                "SELECT execution_location, COUNT(*) as cnt FROM tasks GROUP BY execution_location"
            ).fetchall()
    return {r["execution_location"]: r["cnt"] for r in rows}


def count_by_type() -> Dict[str, int]:
    with _get_conn() as conn:
        rows = conn.execute(
            "SELECT task_type, COUNT(*) as cnt FROM tasks GROUP BY task_type"
        ).fetchall()
    return {r["task_type"]: r["cnt"] for r in rows}


def get_max_task_id() -> int:
    with _get_conn() as conn:
        row = conn.execute("SELECT MAX(id) as m FROM tasks").fetchone()
    return row["m"] or 0


def get_flow_stats(limit: int = 50) -> Dict[str, int]:
    """最近任务流向统计。"""
    with _get_conn() as conn:
        rows = conn.execute(
            """SELECT execution_location, COUNT(*) as cnt FROM (
                SELECT execution_location FROM tasks ORDER BY id DESC LIMIT ?
            ) GROUP BY execution_location""",
            (limit,),
        ).fetchall()
    stats = {"local": 0, "edge": 0, "cloud": 0}
    for r in rows:
        loc = r["execution_location"]
        if loc in stats:
            stats[loc] = r["cnt"]
    return stats


def collect_experiment_stats(since_id: int, scenario: str, strategy: str) -> Dict[str, Any]:
    """采集某段实验窗口内的任务统计。"""
    with _get_conn() as conn:
        rows = conn.execute(
            """SELECT * FROM tasks WHERE id > ? AND scenario=? AND strategy=?""",
            (since_id, scenario, strategy),
        ).fetchall()
    tasks = [dict(r) for r in rows]
    if not tasks:
        return {
            "total_tasks": 0,
            "avg_latency_ms": 0.0,
            "p95_latency_ms": 0.0,
            "urgent_avg_latency_ms": 0.0,
            "deadline_violation_rate": 0.0,
            "success_rate": 100.0,
            "local_task_count": 0,
            "edge_task_count": 0,
            "cloud_task_count": 0,
            "cloud_bandwidth_kb": 0.0,
            "qos_satisfaction_rate": 0.0,
        }

    latencies = [t["total_latency_ms"] for t in tasks if t.get("total_latency_ms") is not None]
    urgent = [
        t["total_latency_ms"] for t in tasks
        if t.get("priority") == "high" or t.get("task_type") == "smoke_alert"
    ]
    sorted_lat = sorted(latencies) if latencies else [0]
    p95_idx = int(len(sorted_lat) * 0.95)
    p95 = sorted_lat[min(p95_idx, len(sorted_lat) - 1)]

    loc = {"local": 0, "edge": 0, "cloud": 0}
    for t in tasks:
        loc[t.get("execution_location", "edge")] = loc.get(t.get("execution_location", "edge"), 0) + 1

    violations = sum(1 for t in tasks if not t.get("deadline_met"))
    success = sum(1 for t in tasks if t.get("success"))

    cloud_bw = sum(
        t.get("data_size_kb", 0) for t in tasks if t.get("execution_location") == "cloud"
    )

    return {
        "total_tasks": len(tasks),
        "avg_latency_ms": round(sum(latencies) / len(latencies), 2) if latencies else 0,
        "p95_latency_ms": round(p95, 2),
        "urgent_avg_latency_ms": round(sum(urgent) / len(urgent), 2) if urgent else 0,
        "deadline_violation_rate": round(violations / len(tasks) * 100, 2),
        "success_rate": round(success / len(tasks) * 100, 2),
        "local_task_count": loc.get("local", 0),
        "edge_task_count": loc.get("edge", 0),
        "cloud_task_count": loc.get("cloud", 0),
        "cloud_bandwidth_kb": round(cloud_bw, 2),
        "qos_satisfaction_rate": compute_qos_satisfaction_rate(tasks),
    }


def insert_experiment_result(record: Dict[str, Any]) -> None:
    with _get_conn() as conn:
        conn.execute(
            """INSERT INTO experiment_results (
                experiment_id, scenario, strategy, duration_sec, total_tasks,
                avg_latency_ms, p95_latency_ms, urgent_avg_latency_ms,
                deadline_violation_rate, success_rate, local_task_count,
                edge_task_count, cloud_task_count, cloud_bandwidth_kb,
                edge_cpu_percent, cloud_cpu_percent, alert_count, qos_satisfaction_rate, timestamp
            ) VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?)""",
            (
                record["experiment_id"], record["scenario"], record["strategy"],
                record["duration_sec"], record["total_tasks"],
                record["avg_latency_ms"], record["p95_latency_ms"],
                record["urgent_avg_latency_ms"], record["deadline_violation_rate"],
                record["success_rate"], record["local_task_count"],
                record["edge_task_count"], record["cloud_task_count"],
                record["cloud_bandwidth_kb"], record["edge_cpu_percent"],
                record["cloud_cpu_percent"], record["alert_count"],
                record.get("qos_satisfaction_rate", 0),
                record["timestamp"],
            ),
        )
        conn.commit()


def get_experiment_results(limit: int = 100) -> List[Dict[str, Any]]:
    with _get_conn() as conn:
        rows = conn.execute(
            "SELECT * FROM experiment_results ORDER BY id DESC LIMIT ?", (limit,)
        ).fetchall()
    return [dict(r) for r in rows]


def get_metrics_from_db() -> Dict[str, Any]:
    return get_metrics_scoped("all")


def compute_qos_satisfaction_rate(tasks: List[Dict[str, Any]]) -> float:
    """QoS Satisfaction Rate = 0.5*deadline_met + 0.3*urgent_success + 0.2*overall_success。"""
    if not tasks:
        return 0.0
    n = len(tasks)
    deadline_met = sum(1 for t in tasks if t.get("deadline_met")) / n * 100
    overall_success = sum(1 for t in tasks if t.get("success")) / n * 100

    urgent = [
        t for t in tasks
        if t.get("priority") == "high" or t.get("task_type") == "smoke_alert"
    ]
    if urgent:
        urgent_ok = sum(
            1 for t in urgent if t.get("success") and t.get("deadline_met")
        ) / len(urgent) * 100
    else:
        urgent_ok = deadline_met

    return round(deadline_met * 0.5 + urgent_ok * 0.3 + overall_success * 0.2, 2)


def _aggregate_tasks(tasks: List[Dict[str, Any]]) -> Dict[str, Any]:
    """从任务列表聚合指标。"""
    if not tasks:
        return {
            "total_tasks": 0,
            "success_rate": 100.0,
            "deadline_violation_rate": 0.0,
            "avg_latency_ms": 0.0,
            "p95_latency_ms": 0.0,
            "emergency_avg_latency_ms": 0.0,
            "edge_task_count": 0,
            "cloud_task_count": 0,
            "local_task_count": 0,
            "task_type_distribution": {},
            "qos_satisfaction_rate": 0.0,
        }

    latencies = [t["total_latency_ms"] for t in tasks if t.get("total_latency_ms") is not None]
    urgent = [
        t["total_latency_ms"] for t in tasks
        if t.get("priority") == "high" or t.get("task_type") == "smoke_alert"
    ]
    sorted_lat = sorted(latencies) if latencies else [0]
    p95_idx = int(len(sorted_lat) * 0.95)
    p95 = sorted_lat[min(p95_idx, len(sorted_lat) - 1)]

    loc = {"local": 0, "edge": 0, "cloud": 0}
    type_dist: Dict[str, int] = {}
    violations = success = 0
    for t in tasks:
        loc[t.get("execution_location", "edge")] = loc.get(t.get("execution_location", "edge"), 0) + 1
        tt = t.get("task_type", "unknown")
        type_dist[tt] = type_dist.get(tt, 0) + 1
        if not t.get("deadline_met"):
            violations += 1
        if t.get("success"):
            success += 1

    n = len(tasks)
    return {
        "total_tasks": n,
        "success_rate": round(success / n * 100, 2),
        "deadline_violation_rate": round(violations / n * 100, 2),
        "avg_latency_ms": round(sum(latencies) / len(latencies), 2) if latencies else 0,
        "p95_latency_ms": round(p95, 2),
        "emergency_avg_latency_ms": round(sum(urgent) / len(urgent), 2) if urgent else 0,
        "edge_task_count": loc.get("edge", 0),
        "cloud_task_count": loc.get("cloud", 0),
        "local_task_count": loc.get("local", 0),
        "task_type_distribution": type_dist,
        "qos_satisfaction_rate": compute_qos_satisfaction_rate(tasks),
    }


def get_latest_experiment_id() -> Optional[str]:
    with _get_conn() as conn:
        row = conn.execute(
            "SELECT experiment_id FROM experiment_results ORDER BY id DESC LIMIT 1"
        ).fetchone()
    return row["experiment_id"] if row else None


def get_metrics_from_experiment(experiment_id: str) -> Dict[str, Any]:
    """从 experiment_results 表聚合最近一次实验指标。"""
    with _get_conn() as conn:
        rows = conn.execute(
            "SELECT * FROM experiment_results WHERE experiment_id=? ORDER BY id",
            (experiment_id,),
        ).fetchall()
    if not rows:
        return {"empty": True}

    results = [dict(r) for r in rows]
    total_tasks = sum(r.get("total_tasks", 0) for r in results)
    if total_tasks == 0:
        return {"empty": True, "experiment_id": experiment_id}

    weighted_lat = sum(r.get("avg_latency_ms", 0) * r.get("total_tasks", 0) for r in results)
    strategy_comparison = {}
    for r in results:
        strategy_comparison[r["strategy"]] = {
            "avg_latency_ms": r.get("avg_latency_ms", 0),
            "count": r.get("total_tasks", 0),
            "p95_latency_ms": r.get("p95_latency_ms", 0),
        }

    return {
        "empty": False,
        "experiment_id": experiment_id,
        "total_tasks": total_tasks,
        "avg_latency_ms": round(weighted_lat / total_tasks, 2),
        "p95_latency_ms": round(max(r.get("p95_latency_ms", 0) for r in results), 2),
        "emergency_avg_latency_ms": round(
            sum(r.get("urgent_avg_latency_ms", 0) for r in results) / len(results), 2
        ),
        "success_rate": round(sum(r.get("success_rate", 100) for r in results) / len(results), 2),
        "deadline_violation_rate": round(
            sum(r.get("deadline_violation_rate", 0) for r in results) / len(results), 2
        ),
        "local_task_count": sum(r.get("local_task_count", 0) for r in results),
        "edge_task_count": sum(r.get("edge_task_count", 0) for r in results),
        "cloud_task_count": sum(r.get("cloud_task_count", 0) for r in results),
        "task_type_distribution": {},
        "strategy_comparison": strategy_comparison,
        "experiment_rows": results,
        "qos_satisfaction_rate": round(
            sum(r.get("qos_satisfaction_rate", 0) * r.get("total_tasks", 0) for r in results)
            / max(total_tasks, 1),
            2,
        ),
    }


def get_metrics_scoped(scope: str = "all") -> Dict[str, Any]:
    """按数据范围返回指标。"""
    if scope == "recent_100":
        tasks = get_recent_tasks(100)
        agg = _aggregate_tasks(tasks)
        agg.update(get_alert_counts())
        agg["data_scope"] = scope
        return agg
    if scope == "recent_300":
        tasks = get_recent_tasks(300)
        agg = _aggregate_tasks(tasks)
        agg.update(get_alert_counts())
        agg["data_scope"] = scope
        return agg
    if scope == "latest_experiment":
        exp_id = get_latest_experiment_id()
        if not exp_id:
            return {"empty": True, "data_scope": scope, **get_alert_counts(), "alert_count": 0}
        exp_metrics = get_metrics_from_experiment(exp_id)
        if exp_metrics.get("empty"):
            return {"empty": True, "data_scope": scope, **get_alert_counts()}
        exp_metrics.update(get_alert_counts())
        exp_metrics["data_scope"] = scope
        return exp_metrics

    # all
    with _get_conn() as conn:
        total = conn.execute("SELECT COUNT(*) as c FROM tasks").fetchone()["c"]
        success = conn.execute("SELECT COUNT(*) as c FROM tasks WHERE success=1").fetchone()["c"]
        deadline_violations = conn.execute(
            "SELECT COUNT(*) as c FROM tasks WHERE deadline_met=0"
        ).fetchone()["c"]
        avg_lat = conn.execute("SELECT AVG(total_latency_ms) as a FROM tasks").fetchone()["a"] or 0.0
        emergency_avg = conn.execute(
            """SELECT AVG(total_latency_ms) as a FROM tasks
               WHERE priority='high' OR task_type='smoke_alert'"""
        ).fetchone()["a"] or 0.0

    alert_counts = get_alert_counts()
    latencies = get_task_latencies(500)
    p95 = 0.0
    if latencies:
        sorted_lat = sorted(latencies)
        idx = int(len(sorted_lat) * 0.95)
        p95 = sorted_lat[min(idx, len(sorted_lat) - 1)]

    loc = count_by_location()
    all_tasks = get_recent_tasks(min(total, 5000) if total else 0)
    return {
        "total_tasks": total,
        "success_rate": (success / total * 100) if total else 100.0,
        "deadline_violation_rate": (deadline_violations / total * 100) if total else 0.0,
        "avg_latency_ms": round(avg_lat, 2),
        "p95_latency_ms": round(p95, 2),
        "emergency_avg_latency_ms": round(emergency_avg, 2),
        "edge_task_count": loc.get("edge", 0),
        "cloud_task_count": loc.get("cloud", 0),
        "local_task_count": loc.get("local", 0),
        "task_type_distribution": count_by_type(),
        "qos_satisfaction_rate": compute_qos_satisfaction_rate(all_tasks),
        "data_scope": "all",
        **alert_counts,
    }


def backup_database() -> Path:
    """备份数据库到 backups/ 目录。"""
    BACKUPS_DIR.mkdir(parents=True, exist_ok=True)
    ts = datetime.now().strftime("%Y%m%d_%H%M%S")
    dest = BACKUPS_DIR / f"computernet_{ts}.db"
    if DB_PATH.exists():
        shutil.copy2(DB_PATH, dest)
    return dest


def reset_demo_tables() -> Dict[str, str]:
    """清空演示相关表，保留表结构。"""
    init_db()
    tables = ["tasks", "alerts", "experiment_results", "strategy_stats"]
    cleared = {}
    with _get_conn() as conn:
        for table in tables:
            try:
                conn.execute(f"DELETE FROM {table}")
                cleared[table] = "ok"
            except sqlite3.OperationalError:
                cleared[table] = "skipped"
        conn.commit()
    return cleared
