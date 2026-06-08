"""DQN-like agent — Fitted Q Iteration + RandomForestRegressor。"""
import logging
from collections import deque
from datetime import datetime
from pathlib import Path
from typing import Any, Deque, Dict, List, Optional, Tuple

import joblib
import numpy as np
from sklearn.ensemble import RandomForestRegressor

from backend.rl.offload_env import OffloadEnv
from backend.rl.state_encoder import ACTIONS, StateEncoder, action_to_location

logger = logging.getLogger("rl.agent")

MODEL_TYPE = "sklearn_fitted_q"


class LateRLAgent:
    """轻量 epsilon-greedy Fitted-Q agent。"""

    def __init__(
        self,
        state_dim: int = None,
        gamma: float = 0.95,
        epsilon: float = 1.0,
        epsilon_min: float = 0.05,
        epsilon_decay: float = 0.995,
        batch_size: int = 64,
        replay_capacity: int = 10000,
    ):
        self.encoder = StateEncoder()
        self.state_dim = state_dim or self.encoder.state_dim
        self.gamma = gamma
        self.epsilon = epsilon
        self.epsilon_min = epsilon_min
        self.epsilon_decay = epsilon_decay
        self.batch_size = batch_size
        self.replay: Deque[Tuple[np.ndarray, int, float, np.ndarray]] = deque(maxlen=replay_capacity)
        self.models: List[RandomForestRegressor] = [
            RandomForestRegressor(n_estimators=32, max_depth=10, random_state=42 + i, n_jobs=-1)
            for i in range(len(ACTIONS))
        ]
        self._fitted = False

    def predict_q_values(self, state: np.ndarray) -> np.ndarray:
        state = np.asarray(state, dtype=np.float64).reshape(1, -1)
        if not self._fitted:
            return np.array([0.0, 0.1, 0.05])
        qs = np.array([float(m.predict(state)[0]) for m in self.models])
        return qs

    def act(self, state: np.ndarray, epsilon: Optional[float] = None) -> int:
        eps = self.epsilon if epsilon is None else epsilon
        if np.random.random() < eps:
            return int(np.random.randint(len(ACTIONS)))
        q = self.predict_q_values(state)
        return int(np.argmax(q))

    def remember(self, s, a, r, s_next) -> None:
        self.replay.append((np.array(s), int(a), float(r), np.array(s_next)))

    def _fit_models(self) -> None:
        if len(self.replay) < self.batch_size:
            return
        batch = list(self.replay)
        if len(batch) > 2000:
            batch = batch[-2000:]
        states = np.vstack([b[0] for b in batch])
        for action_id in range(len(ACTIONS)):
            xs, ys = [], []
            for s, a, r, s_next in batch:
                if a != action_id:
                    continue
                target = r
                if self._fitted:
                    q_next = self.predict_q_values(s_next)
                    target = r + self.gamma * float(np.max(q_next))
                xs.append(s)
                ys.append(target)
            if len(xs) < 10:
                continue
            self.models[action_id].fit(np.vstack(xs), np.array(ys))
        self._fitted = True

    def train(
        self,
        env: OffloadEnv,
        episodes: int = 200,
        episode_length: int = 200,
    ) -> List[Dict[str, Any]]:
        """训练并返回每 episode 统计。"""
        curve: List[Dict[str, Any]] = []
        best_avg = float("-inf")

        for ep in range(1, episodes + 1):
            state = env.reset()
            total_reward = 0.0
            latencies: List[float] = []
            violations = 0
            action_counts = [0, 0, 0]

            for _ in range(episode_length):
                action = self.act(state)
                next_state, reward, _, info = env.step(action)
                self.remember(state, action, reward, next_state)
                total_reward += reward
                latencies.append(info["latency_ms"])
                if not info["deadline_met"]:
                    violations += 1
                action_counts[action] += 1
                state = next_state

            if ep % 2 == 0 or ep == episodes:
                self._fit_models()

            self.epsilon = max(self.epsilon_min, self.epsilon * self.epsilon_decay)
            avg_lat = sum(latencies) / max(len(latencies), 1)
            viol_rate = violations / max(episode_length, 1)
            record = {
                "episode": ep,
                "total_reward": round(total_reward, 4),
                "avg_latency": round(avg_lat, 2),
                "deadline_violation_rate": round(viol_rate, 4),
                "local_actions": action_counts[0],
                "edge_actions": action_counts[1],
                "cloud_actions": action_counts[2],
                "epsilon": round(self.epsilon, 4),
            }
            curve.append(record)
            best_avg = max(best_avg, total_reward)
            if ep % max(1, episodes // 10) == 0 or ep == episodes:
                logger.info(
                    "Episode %d/%d reward=%.2f eps=%.3f viol=%.2f",
                    ep, episodes, total_reward, self.epsilon, viol_rate,
                )
        curve[-1]["best_avg_reward"] = best_avg
        return curve

    def save(self, path: Path, metadata: Dict[str, Any]) -> None:
        path.parent.mkdir(parents=True, exist_ok=True)
        payload = {
            "models": self.models,
            "meta": metadata,
            "encoder_state_dim": self.encoder.state_dim,
            "fitted": self._fitted,
        }
        joblib.dump(payload, path)

    def load(self, path: Path) -> Dict[str, Any]:
        payload = joblib.load(path)
        self.models = payload["models"]
        self._fitted = payload.get("fitted", True)
        return payload.get("meta", {})

    @staticmethod
    def action_distribution(curve: List[Dict[str, Any]]) -> Dict[str, float]:
        if not curve:
            return {"local": 0, "edge": 0, "cloud": 0}
        last = curve[-10:] if len(curve) >= 10 else curve
        loc = sum(r["local_actions"] for r in last)
        edge = sum(r["edge_actions"] for r in last)
        cloud = sum(r["cloud_actions"] for r in last)
        total = max(loc + edge + cloud, 1)
        return {
            "local": round(loc / total, 4),
            "edge": round(edge / total, 4),
            "cloud": round(cloud / total, 4),
        }
