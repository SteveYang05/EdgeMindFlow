"""数据集注册表。"""
from typing import Any, Dict, List

# auto_download=True 的会在启动/POST download 时自动尝试
DATASET_REGISTRY: Dict[str, Dict[str, Any]] = {
    "mec_edge": {
        "name": "mec_edge",
        "display_name": "Mobile Edge Computing Trace (MEC)",
        "description": "边缘计算任务 trace（默认从公开 Mobile Edge Computing Dataset 下载并转换为项目 schema）",
        "auto_download": True,
        "size_class": "small",
        "format": "csv",
        "filename": "mec_edge_tasks.csv",
        "url_env": "MEC_EDGE_DATASET_URL",
        "default_url": "https://raw.githubusercontent.com/nicsdee/Mobile-Edge-Computing-Dataset/main/mobile_edge_dataset.csv",
        "doc_url": "https://github.com/nicsdee/Mobile-Edge-Computing-Dataset",
        "remote_repo": "nicsdee/Mobile-Edge-Computing-Dataset",
        "fields": [
            "timestamp", "device_id", "task_type", "priority",
            "data_size_kb", "compute_cost", "deadline_ms",
            "edge_cpu_load", "network_delay_ms",
        ],
    },
    "eua": {
        "name": "eua",
        "display_name": "EUA Dataset (Edge User Allocation)",
        "description": "边缘用户分配 trace，含用户位置与边缘节点映射",
        "auto_download": True,
        "size_class": "small",
        "format": "csv",
        "filename": "eua_users.csv",
        "url_env": "EUA_DATASET_URL",
        "default_url": "https://raw.githubusercontent.com/PhuLai/eua-dataset/master/users/users-melbcbd-generated.csv",
        "secondary_url": "https://raw.githubusercontent.com/PhuLai/eua-dataset/master/edge-servers/site-optus-melbCBD.csv",
        "secondary_url_env": "EUA_EDGE_SITES_URL",
        "doc_url": "https://github.com/PhuLai/eua-dataset",
        "remote_repo": "PhuLai/eua-dataset",
        "fields": [
            "user_id", "latitude", "longitude", "edge_node_id",
            "request_rate", "avg_data_size_kb", "avg_compute_cost",
        ],
    },
    "google_cluster": {
        "name": "google_cluster",
        "display_name": "Google Cluster Trace",
        "description": "Google 大规模集群 trace（仅文档与 API 注册，不默认下载）",
        "auto_download": False,
        "size_class": "large",
        "format": "csv/trace",
        "filename": None,
        "url_env": "GOOGLE_CLUSTER_TRACE_URL",
        "default_url": "https://github.com/google/cluster-data",
        "doc_url": "https://github.com/google/cluster-data/blob/master/ClusterData2011_2.md",
        "manual_only": True,
        "note": "体积过大，请自行下载后放置于 data/traces/google_cluster/",
    },
    "alibaba_cluster": {
        "name": "alibaba_cluster",
        "display_name": "Alibaba Cluster Trace",
        "description": "阿里巴巴集群 trace（仅文档与 API 注册，不默认下载）",
        "auto_download": False,
        "size_class": "large",
        "format": "csv/trace",
        "filename": None,
        "url_env": "ALIBABA_CLUSTER_TRACE_URL",
        "default_url": "https://github.com/alibaba/clusterdata",
        "doc_url": "https://github.com/alibaba/clusterdata",
        "manual_only": True,
        "note": "体积过大，请自行下载后放置于 data/traces/alibaba_cluster/",
    },
}


def list_datasets() -> List[Dict[str, Any]]:
    return list(DATASET_REGISTRY.values())


def get_dataset(name: str) -> Dict[str, Any]:
    if name not in DATASET_REGISTRY:
        raise KeyError(f"Unknown dataset: {name}")
    return DATASET_REGISTRY[name]


def auto_download_names() -> List[str]:
    return [k for k, v in DATASET_REGISTRY.items() if v.get("auto_download")]
