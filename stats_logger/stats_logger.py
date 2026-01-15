#!/usr/bin/env python3
import os, time, csv, sys
from datetime import datetime, timezone
from typing import List, Tuple
import docker, threading, os, atexit
from flask import Flask, jsonify, request
import seaborn as sns
import matplotlib.pyplot as plt
import pandas as pd


app = Flask(__name__)

metrics_lock = threading.Lock()

# -------------------- Config (ENV) --------------------
SCRAPE_INTERVAL = float(os.getenv("SCRAPE_INTERVAL", "5"))
RUNNING_CSV_FILE = "prover_system_metrics_running.csv"
# MAX_MEMORY = float(os.getenv("MAX_MEMORY", 100))
# MAX_CPU_PERCENT = float(os.getenv("MAX_CPU_PCT", 2000))

HEADER = [
    "timestamp_utc",
    "container",
    "cpu_pct",
    "mem_usage_bytes",
    "mem_limit_bytes",
    "mem_pct",
    "net_rx_bytes",
    "net_tx_bytes",
    "blk_read_bytes",
    "blk_write_bytes",
    "pids"
]

def ensure_header(path: str):
    if not os.path.exists(path) or os.path.getsize(path) == 0:
        with open(path, "w", newline="", encoding="utf-8") as f:
            w = csv.writer(f)
            w.writerow(HEADER)

def utc_now_iso() -> str:
    return datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")

def resolve_containers(client: docker.DockerClient) -> List[str]:
    """Return list of container names/ids to scrape."""
    # if TARGETS_ENV:
    #     return TARGETS_ENV.split()
    # if SERVICE_NAME:
    #     containers = client.containers.list(
    #         filters={"label": f"com.docker.compose.service={SERVICE_NAME}"}
    #     )
    #     return [c.name for c in containers]
    # default: all running containers (except ourselves if named)
    containers = client.containers.list()
    me = os.getenv("HOSTNAME", "")
    names = []
    for c in containers:
        if me and (c.name == me or c.id.startswith(me)):
            continue
        names.append(c.name)
    return names

def cpu_percent_from_stats(stats: dict) -> float:
    """
    Docker's CPU% formula:
    (cpu_delta / system_delta) * online_cpus * 100
    """
    try:
        cpu_stats = stats.get("cpu_stats", {}) or {}
        precpu = stats.get("precpu_stats", {}) or {}

        cpu_total = cpu_stats.get("cpu_usage", {}).get("total_usage", 0)
        pre_total = precpu.get("cpu_usage", {}).get("total_usage", 0)

        sys_total = cpu_stats.get("system_cpu_usage", 0) or 0
        pre_sys   = precpu.get("system_cpu_usage", 0) or 0

        cpu_delta = float(cpu_total) - float(pre_total)
        sys_delta = float(sys_total) - float(pre_sys)

        online_cpus = cpu_stats.get("online_cpus")
        if not online_cpus:
            per = cpu_stats.get("cpu_usage", {}).get("percpu_usage") or []
            online_cpus = max(len(per), 1)

        if sys_delta > 0 and cpu_delta >= 0:
            return (cpu_delta / sys_delta) * online_cpus * 100.0
    except Exception:
        pass
    return float("nan")

def mem_from_stats(stats: dict) -> Tuple[int, int, float]:
    mem = stats.get("memory_stats", {}) or {}
    usage = int(mem.get("usage") or 0)
    limit = int(mem.get("limit") or 0)
    pct = (usage / limit * 100.0) if limit > 0 else float("nan")
    return usage, limit, pct

def net_from_stats(stats: dict) -> Tuple[int, int]:
    nets = stats.get("networks") or {}
    rx = tx = 0
    for iface, data in nets.items():
        rx += int(data.get("rx_bytes") or 0)
        tx += int(data.get("tx_bytes") or 0)
    return rx, tx

def blkio_from_stats(stats: dict) -> Tuple[int, int]:
    blk = stats.get("blkio_stats", {}) or {}
    entries = blk.get("io_service_bytes_recursive") or []
    read = write = 0
    for e in entries:
        op = (e.get("op") or "").lower()
        val = int(e.get("value") or 0)
        if op == "read":
            read += val
        elif op == "write":
            write += val
    return read, write

def pids_from_stats(stats: dict) -> int:
    return int((stats.get("pids_stats") or {}).get("current") or 0)


def log_metrics():
    client = docker.from_env()
    print(f"Output dir: /prover-stats-logger/results/")
    #print(f"Interval: {SCRAPE_INTERVAL}s | SERVICE_NAME={SERVICE_NAME or '-'} | TARGETS={' '.join(TARGETS_ENV.split()) or '-'}")

    iteration = 0
    targets: List[str] = []

    ensure_header(RUNNING_CSV_FILE)

    while True:
        iteration += 1
        if iteration == 1:
            try:
                targets = resolve_containers(client)
            except Exception as e:
                print(f"[collector] resolve_containers error: {e}", file=sys.stderr)
                targets = []

        ts = utc_now_iso()
        rows = []
        for ref in targets:
            try:
                c = client.containers.get(ref)
                stats = c.stats(stream=False)
                cpu_pct = cpu_percent_from_stats(stats)
                mem_use, mem_lim, mem_pct = mem_from_stats(stats)
                rx, tx = net_from_stats(stats)
                blk_r, blk_w = blkio_from_stats(stats)
                pids = pids_from_stats(stats)

                rows.append([
                    ts, c.name, f"{cpu_pct:.4f}",
                    str(mem_use), str(mem_lim), f"{mem_pct:.4f}" if mem_lim > 0 else "",
                    str(rx), str(tx),
                    str(blk_r), str(blk_w),
                    str(pids),
                ])
            except docker.errors.NotFound:
                # container disappeared between resolve and scrape
                continue
            except Exception as e:
                print(f"error on {ref}: {e}", file=sys.stderr)
                continue

        # Append to per-run file
        if rows:
            with open(RUNNING_CSV_FILE, "a", newline="", encoding="utf-8") as f:
                w = csv.writer(f)
                w.writerows(rows)

        time.sleep(SCRAPE_INTERVAL)

def create_timestamped_folder(root):
    # Get the current timestamp in a suitable format
    timestamp = datetime.now().strftime("%Y%m%d%H%M%S")

    # Create the folder name with the timestamp
    folder_name = os.path.join(root, f"prover-system-snapshot-{timestamp}")

    # Create the folder if it doesn't exist
    if not os.path.exists(folder_name):
        os.makedirs(folder_name)

    return folder_name

def load_df(csv_path):
    df = pd.read_csv(csv_path)
    if df.empty:
        raise SystemExit("CSV is empty")
    df["timestamp_utc"] = pd.to_datetime(df["timestamp_utc"], utc=True, errors="coerce")
    df = df.dropna(subset=["timestamp_utc"])
    for col in ["cpu_pct", "mem_usage_bytes"]:
        df[col] = pd.to_numeric(df[col], errors="coerce")
    df["mem_gib"] = df["mem_usage_bytes"] / (1024**3)
    df = df.sort_values(["container", "timestamp_utc"])
    return df

def summarize_metrics(container_name,metrics_filename="prover_system_metrics.csv",plot_filename="prover_system_plot.png",outdir="."):

    result_root = create_timestamped_folder(outdir)
    metrics_path = os.path.join(result_root, metrics_filename)
    plot_path = os.path.join(result_root, plot_filename)

    df = load_df(RUNNING_CSV_FILE)
    df.to_csv(metrics_path,index=False)

    with metrics_lock:
        try:
            if os.path.exists(RUNNING_CSV_FILE):
                os.remove(RUNNING_CSV_FILE)
                print(f"File '{RUNNING_CSV_FILE}' cleared successfully")
            else:
                print(f"File '{RUNNING_CSV_FILE}' not found, skipping clearance")
        except Exception as e:
            print(f"Error deleting file '{RUNNING_CSV_FILE}': {e}")

        ensure_header(RUNNING_CSV_FILE)

    sub = df[df["container"] == container_name]
    if sub.empty:
        return ""
    fig, ax = plt.subplots(figsize=(12, 5))
    # Left axis: CPU %
    sns.lineplot(data=sub, x="timestamp_utc", y="cpu_pct", ax=ax, linewidth=2, color="#1f77b4")
    ax.set_xlabel("Time")
    ax.set_ylabel("CPU (%)")
    ax.set_title(f"CPU & Memory Over Time — {container_name}")
    #ax.set_ylim(0, MAX_CPU_PERCENT)

    # Right axis: Memory GiB
    ax2 = ax.twinx()
    sns.lineplot(data=sub, x="timestamp_utc", y="mem_gib", ax=ax2, linewidth=2, color="#d62728")
    ax2.set_ylabel("Memory (GiB)")
    #ax2.set_ylim(0, MAX_MEMORY)

    # Build a combined legend
    cpu_line = ax.lines[0]
    mem_line = ax2.lines[0]
    ax.legend([cpu_line, mem_line], ["CPU (%)", "Memory (GiB)"], loc="best")

    fig.tight_layout()
    os.makedirs(outdir, exist_ok=True)
    plt.savefig(plot_path, dpi=150)
    plt.close(fig)


@app.route('/create-prover-snapshot', methods=['POST'])
def create_regulator_snapshot():
    try:
        data = request.get_json()
        container_name = data.get("container_name","prover-prover")
        summarize_metrics(container_name,outdir="/prover-stats-logger/results/")
        return jsonify({"status": "success", "message": "System metrics snapshot created."}), 200
    except Exception as e:
        return jsonify({"status": "error", "message": str(e)}), 500

if __name__ == '__main__':
    PROVER_PORT = os.getenv("PROVER_STATS_LOGGER_PORT", 5003)
    threading.Thread(target=log_metrics, daemon=True).start()
    atexit.register(summarize_metrics)
    app.run(host='0.0.0.0', port=PROVER_PORT)