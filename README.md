# ego_whole_body_tracking

Workspace for ego whole-body tracking experiments and third-party motion tracking baselines.

## Layout

```text
ego_whole_body_tracking/
└── third-parties/
    └── sqrtVINS/              # rpng/sqrtVINS git submodule
```

Local environments live under `.envs/`, but `.envs/` is intentionally ignored by Git.

## Third-party repositories

`sqrtVINS` is tracked as a Git submodule:

```bash
git submodule update --init --recursive
```

Current submodule URL:

```text
https://github.com/rpng/sqrtVINS
```

## sqrtVINS environment

The current server uses a local Docker-based ROS1 Noetic environment at:

```text
.envs/sqrtVINS-docker
```

This directory is not committed. The reason is that environment folders can contain machine-specific scripts, caches, generated files, or secrets.

The upstream sqrtVINS README targets Ubuntu 20.04 + ROS1/catkin. On Ubuntu 24.04 hosts, prefer Docker or another isolated ROS environment instead of installing ROS directly into the host system.

## Environment naming rule

Environment folders under `.envs/` should use the format:

```text
<target>-<base>
```

Examples:

```text
sqrtVINS-docker
egoAllo-uv
```

Do not commit local secrets such as `.env`.
