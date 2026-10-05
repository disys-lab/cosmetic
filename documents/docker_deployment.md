# Docker Deployment

CoSMeTIC ships with a two-container Docker stack. This is the recommended way to run the proof APIs in a shared or production environment.

---

## Containers

| Container name | Image | Role |
|----------------|-------|------|
| `zkpprover` | `anon2026dpeval/cosmeticprover:latest` | Runs all three Flask APIs (ACC / KS / LRT) |
| `prover-stats-logger` | `anon2026dpeval/cosmeticstatslogger:latest` | Collects CPU/memory and Docker container stats during proof generation |
| `COSMeTICprover-input-files` | `anon2026dpeval/cosmeticprover:latest` | Runs the read-only Input Files API (`api_input_files.py`) on port `5015` (see [API Reference §10](api_reference.md#10-input-files-api-port-5015)) |

Both containers share a Docker named volume `results_data` so proof outputs and stats logs land in the same place.

---

## Prerequisites

- Docker Engine installed and running
- Docker Compose (`docker compose ...` — V2 syntax)
- Ports `5012`, `5013`, `5014`, `5015`, and `5003` available on the host

---

## Pulling images

Pre-built images are on Docker Hub. You do not need to build locally unless you have modified the source code.

Docker Hub enforces pull-rate limits for unauthenticated users. Log in first:

```bash
docker login
```

Then pull:

```bash
docker pull anon2026dpeval/cosmeticprover:latest
docker pull anon2026dpeval/cosmeticstatslogger:latest
```

---

## Starting the stack

From the directory containing `docker-compose.yml`:

```bash
docker compose up -d
```

Verify both containers are running:

```bash
docker ps
```

---

## Environment variables

### Prover container (`zkpprover`)

| Variable | Default in compose | Purpose |
|----------|--------------------|---------|
| `API_acc_port` | `5012` | Port the ACC Flask app listens on inside the container |
| `API_ks_port` | `5013` | Port the KS Flask app listens on |
| `API_lrt_port` | `5014` | Port the LRT Flask app listens on |
| `STATS_LOGGER_URL` | `http://prover-stats-logger:5003` | URL the prover calls to trigger stat snapshots |

### Stats logger container (`prover-stats-logger`)

| Variable | Default | Purpose |
|----------|---------|---------|
| `TARGET_CONTAINER` | `zkpprover` | Docker container name to monitor |
| `SAMPLE_INTERVAL` | (set in compose) | Seconds between process-level stat samples |
| `DOCKER_SCRAPE_INTERVAL` | (set in compose) | Seconds between Docker-level stat scrapes |

### Input files container (`COSMeTICprover-input-files`)

| Variable | Default in compose | Purpose |
|----------|--------------------|---------|
| `API_input_files_port` | `5015` | Port the Input Files Flask app listens on |

---

## Where results are stored

| Service | Path inside container | Mapped to |
|---------|-----------------------|-----------|
| Prover | `/app/results` | `results_data` volume |
| Stats logger | `/prover-stats-logger/results` | `results_data` volume |
| Prover (proofs) | `/app/proofs` | `./proofs` on the host (bind mount) |
| Input files | `/app/proofs` | `./proofs` on the host (same folder, read-only use) |
| Prover (input datasets) | `/app/data` | `./data` on the host (bind mount) |

The prover image does not include the `data/` datasets, so `docker-compose.yml` bind-mounts the repository's `./data` folder to `/app/data`. Without it, setup fails with `No such file or directory: './data/...pkl'`.

Proof artifacts (keys, compiled circuits, `proof-results-*` folders) are written to `/app/proofs`, which `docker-compose.yml` bind-mounts to `./proofs` next to the compose file. They are therefore visible directly on the host and are kept after `docker compose down -v`.

The compose file also bind-mounts `api_acc_test.py`, `api_ks_test.py`, `api_lrt_test.py`, and `api_input_files.py` from the checkout over the copies in the image, so edits to those files take effect after `docker compose restart` without rebuilding. Changes to other code (e.g. `modules/`, `merkletree/`) still require rebuilding the image.

To access results from the host, either:

- `docker cp zkpprover:/app/results ./local-results`
- Or replace the volume with a bind mount in `docker-compose.yml`:

```yaml
volumes:
  - ./results:/app/results
```

---

## Stopping the stack

```bash
docker compose down
```

To also remove the shared volume (permanently deletes saved proofs and stats):

```bash
docker compose down -v
```

---

## Building images locally (Makefile)

If you have modified the source code, rebuild the images with:

```bash
# Build both images
make build

# Build only the prover image
make build-prover

# Build only the stats logger image
make build-statslogger
```

Then bring the stack back up:

```bash
docker compose up -d
```

### Image tags produced by `make build`

| Target | Image tag |
|--------|-----------|
| Prover | `anon2026dpeval/cosmeticprover:latest` |
| Stats logger | `anon2026dpeval/cosmeticstatslogger:latest` |

---

## Checking logs

```bash
# Prover logs
docker logs zkpprover -f

# Stats logger logs
docker logs prover-stats-logger -f
```

---

## Networking

Both containers are on the same Docker Compose network (`default`). The prover resolves the stats logger by the container service name `prover-stats-logger` (as set in `STATS_LOGGER_URL`). No external network exposure is needed for inter-container communication.

The prover's three API ports (`5012`, `5013`, `5014`), the input files port (`5015`), and the stats logger port (`5003`) are published to the host, making them accessible from outside the containers.
