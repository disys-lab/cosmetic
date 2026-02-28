# `stats_logger.py` — `stats_logger/stats_logger.py`

A lightweight sidecar Flask service that continuously scrapes Docker container resource metrics (CPU, memory, network, block I/O) in a background thread and exposes an HTTP endpoint to snapshot and plot those metrics on demand.

In the Docker Compose stack, this service monitors the `zkpprover` container and is triggered by the prover APIs at the start and end of each proof job.

## Configuration

| Environment variable | Default | Description |
|----------------------|---------|-------------|
| `SCRAPE_INTERVAL` | `5` | Seconds between Docker stats scrapes. |
| `PROVER_STATS_LOGGER_PORT` | `5003` | Port the Flask app listens on. |

**Runtime CSV file:** `prover_system_metrics_running.csv` — appended to continuously during the scrape loop.

**CSV columns:**

| Column | Description |
|--------|-------------|
| `timestamp_utc` | ISO 8601 UTC timestamp. |
| `container` | Docker container name. |
| `cpu_pct` | CPU usage percentage. |
| `mem_usage_bytes` | Memory used (bytes). |
| `mem_limit_bytes` | Memory limit (bytes). |
| `mem_pct` | Memory usage as a percentage of the limit. |
| `net_rx_bytes` | Total network bytes received across all interfaces. |
| `net_tx_bytes` | Total network bytes sent. |
| `blk_read_bytes` | Total block I/O bytes read. |
| `blk_write_bytes` | Total block I/O bytes written. |
| `pids` | Number of processes/threads in the container. |

---

## Module-level helpers

### `ensure_header(path)`

Writes the CSV header row to `path` if the file does not exist or is empty.

| Parameter | Type | Description |
|-----------|------|-------------|
| `path` | `str` | Path to the CSV file. |

---

### `utc_now_iso()`

Returns the current UTC time as an ISO 8601 string (`YYYY-MM-DDTHH:MM:SSZ`).

**Returns** `str`.

---

### `resolve_containers(client)`

Lists all running Docker containers visible to the local Docker socket, excluding the stats logger's own container (identified by the `HOSTNAME` environment variable).

| Parameter | Type | Description |
|-----------|------|-------------|
| `client` | `docker.DockerClient` | Docker SDK client connected to the local socket. |

**Returns** `list[str]` — container names to scrape.

---

### `cpu_percent_from_stats(stats)`

Computes CPU usage percentage from a raw Docker stats dict using Docker's standard formula:

```
cpu_pct = (cpu_delta / sys_delta) * online_cpus * 100
```

| Parameter | Type | Description |
|-----------|------|-------------|
| `stats` | `dict` | Raw output from `container.stats(stream=False)`. |

**Returns** `float` — CPU percentage, or `float("nan")` on any parse error.

---

### `mem_from_stats(stats)`

Extracts memory usage, limit, and percentage from a raw Docker stats dict.

| Parameter | Type | Description |
|-----------|------|-------------|
| `stats` | `dict` | Raw Docker stats. |

**Returns** `tuple[int, int, float]` — `(usage_bytes, limit_bytes, pct)`.

---

### `net_from_stats(stats)`

Sums network bytes across all interfaces from a raw Docker stats dict.

| Parameter | Type | Description |
|-----------|------|-------------|
| `stats` | `dict` | Raw Docker stats. |

**Returns** `tuple[int, int]` — `(rx_bytes, tx_bytes)`.

---

### `blkio_from_stats(stats)`

Sums block I/O read and write bytes from a raw Docker stats dict.

| Parameter | Type | Description |
|-----------|------|-------------|
| `stats` | `dict` | Raw Docker stats. |

**Returns** `tuple[int, int]` — `(read_bytes, write_bytes)`.

---

### `pids_from_stats(stats)`

Extracts the process count from a raw Docker stats dict.

| Parameter | Type | Description |
|-----------|------|-------------|
| `stats` | `dict` | Raw Docker stats. |

**Returns** `int`.

---

## Background scrape loop

### `log_metrics()`

Long-running function run in a daemon background thread. On the first iteration, resolves the set of containers to monitor, then enters an infinite loop:

1. Calls `container.stats(stream=False)` for each target container.
2. Computes CPU, memory, network, block I/O, and PID metrics.
3. Appends a row to `prover_system_metrics_running.csv`.
4. Sleeps for `SCRAPE_INTERVAL` seconds.

Target containers are resolved only once (on the first iteration). If a container disappears between resolution and scraping, `docker.errors.NotFound` is silently caught and that container is skipped.

---

## Snapshot helpers

### `create_timestamped_folder(root)`

Creates a timestamped subfolder under `root` named `prover-system-snapshot-YYYYMMDDHHMMSS`.

| Parameter | Type | Description |
|-----------|------|-------------|
| `root` | `str` | Parent directory for the snapshot folder. |

**Returns** `str` — path to the created folder.

---

### `load_df(csv_path)`

Reads the running CSV file into a `pandas.DataFrame`, parses timestamps, and converts `cpu_pct` and `mem_usage_bytes` to numeric. Adds a `mem_gib` column (memory in GiB).

| Parameter | Type | Description |
|-----------|------|-------------|
| `csv_path` | `str` | Path to the CSV file to read. |

**Returns** `pandas.DataFrame` sorted by `(container, timestamp_utc)`.

**Raises** `SystemExit` if the CSV is empty.

---

### `summarize_metrics(container_name, metrics_filename, plot_filename, outdir)`

Generates a snapshot: saves the current running CSV to a new timestamped folder, clears the running CSV, and produces a dual-axis line plot of CPU and memory usage.

| Parameter | Type | Default | Description |
|-----------|------|---------|-------------|
| `container_name` | `str` | — | Name of the Docker container to plot (filters the DataFrame). |
| `metrics_filename` | `str` | `"prover_system_metrics.csv"` | Filename for the saved CSV snapshot. |
| `plot_filename` | `str` | `"prover_system_plot.png"` | Filename for the PNG plot. |
| `outdir` | `str` | `"."` | Root directory under which the timestamped snapshot folder is created. |

**Plot details:**

- Left Y-axis (blue): CPU percentage over time.
- Right Y-axis (red): Memory in GiB over time.
- The running CSV is cleared and a fresh header is written after each snapshot (protected by `metrics_lock` to avoid race conditions with the scrape thread).

---

## Flask API

### `POST /create-prover-snapshot`

Triggers an immediate metrics snapshot for a specified container.

**Request body (JSON):**

| Field | Type | Default | Description |
|-------|------|---------|-------------|
| `container_name` | `str` | `"prover-prover"` | Name of the Docker container to snapshot. |

**Response (200):**

```json
{"status": "success", "message": "System metrics snapshot created."}
```

**Response (500):**

```json
{"status": "error", "message": "<exception message>"}
```

**Side effects:** Calls `summarize_metrics(container_name, outdir="/prover-stats-logger/results/")`, which saves a CSV + PNG to a timestamped folder and resets the running CSV.

---

## Entry point (`__main__`)

```python
if __name__ == '__main__':
    PROVER_PORT = os.getenv("PROVER_STATS_LOGGER_PORT", 5003)
    threading.Thread(target=log_metrics, daemon=True).start()
    atexit.register(summarize_metrics)
    app.run(host='0.0.0.0', port=PROVER_PORT)
```

On startup:

1. Launches `log_metrics()` as a daemon background thread.
2. Registers `summarize_metrics` as an `atexit` handler (saves a final snapshot on shutdown).
3. Starts the Flask server on `0.0.0.0:<PROVER_STATS_LOGGER_PORT>`.
