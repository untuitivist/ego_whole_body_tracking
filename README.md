# ego_whole_body_tracking

Workspace for ego whole-body tracking experiments and third-party motion tracking baselines.

## Layout

```text
ego_whole_body_tracking/
├── workflow/                 # Project-level scripts and adapters
└── third-parties/
    ├── sqrtVINS/             # rpng/sqrtVINS git submodule
    └── egoallo/              # brentyi/egoallo git submodule
```

Local environments live under `.envs/`, but `.envs/` is intentionally ignored by Git.

## Third-party repositories

Third-party baselines are tracked as Git submodules:

```bash
git submodule update --init --recursive
```

Current submodules:

```text
https://github.com/rpng/sqrtVINS
https://github.com/brentyi/egoallo
```

## Local environments

Environment folders under `.envs/` should use the format:

```text
<target>-<base>
```

Current local environments on the EC2 instance:

```text
.envs/sqrtVINS-docker
.envs/egoallo-uv
```

These directories are not committed. They may contain machine-specific scripts, caches, generated files, model/data paths, or secrets.

### sqrtVINS

The upstream sqrtVINS README targets Ubuntu 20.04 + ROS1/catkin. On Ubuntu 24.04 hosts, prefer Docker or another isolated ROS environment instead of installing ROS directly into the host system.

### EgoAllo

EgoAllo requires Python 3.12 or newer. The current EC2 environment is being built with `uv` under `.envs/egoallo-uv` from:

```bash
third-parties/egoallo/pyproject.toml
```

Inference-specific extras from the upstream README, such as JAX CUDA, `jaxls`, checkpoints, sample trajectories, and SMPL-H model files, should be handled explicitly when needed rather than committed into this repository.

Do not commit local secrets such as `.env`.
