# ego_whole_body_tracking

Workspace for ego whole-body tracking experiments and third-party motion tracking baselines.

## Layout

```text
ego_whole_body_tracking/
├── workflow/                 # Project-level scripts and adapters
└── third-parties/
    ├── sqrtVINS/             # rpng/sqrtVINS git submodule
    ├── egoallo/              # brentyi/egoallo git submodule
    └── HaWoR/                # ThunderVVV/HaWoR git submodule
```

Local environments and benchmark clips live under `.envs/` and `datas/`; both are intentionally ignored by Git.

## Third-party repositories

Third-party baselines are tracked as Git submodules:

```bash
git submodule update --init --recursive
```

Current submodules:

```text
https://github.com/rpng/sqrtVINS
https://github.com/brentyi/egoallo
https://github.com/ThunderVVV/HaWoR
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
.envs/hawor-uv
```

EgoAllo and HaWoR should not share one Python environment by default. EgoAllo requires Python 3.12+ and currently installs Torch 2.7.1, while HaWoR's README targets Python 3.10, Torch 1.13.0 + CUDA 11.7, NumPy 1.26.4, and several CUDA/C++ extensions. Keep them separate until a compatibility pass proves otherwise.

## Local benchmark data

Benchmark clips are stored locally under `datas/` and ignored by Git. Current EC2 benchmark data:

```text
datas/20260508_050222_session1_random_10s
```

This mirrors:

```text
Z:\DATASETS\Frodobots\robocap_lab\20260508_050222_session1_random_10s
```

Do not commit local secrets such as `.env`, model checkpoints, or dataset files.
