# MQTT 通信模块

## Topic 设计

```
smart_park/devices/{device_id}/tasks
```

## 方案 A：轻量 MQTT（可选）

1. 启动 broker：`python mqtt/broker.py`
2. 设置环境变量：`export COMM_MODE=mqtt`
3. 重启系统

## 方案 B：HTTP Fallback（默认）

本项目**默认使用 HTTP fallback**，无需安装 Mosquitto：

```
POST http://localhost:8000/api/tasks/submit
```

请求体仍保留 `topic` 字段，体现 MQTT 架构设计。

## 切换方式

在 `scripts/start_all.sh` 中修改 `COMM_MODE` 环境变量即可。
