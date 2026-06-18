# ego_whole_body_tracking

用于 ego whole-body tracking 实验和第三方运动跟踪基线的工作区。

## 目录结构

```text
ego_whole_body_tracking/
├── workflow/                 # 项目级脚本和适配层
└── third-parties/
    ├── sqrtVINS/             # rpng/sqrtVINS git submodule
    └── egoallo/              # brentyi/egoallo git submodule
```

本地环境统一放在 `.envs/` 下，但 `.envs/` 会被 Git 忽略。

## 第三方仓库

第三方基线通过 Git submodule 管理：

```bash
git submodule update --init --recursive
```

当前 submodule：

```text
https://github.com/rpng/sqrtVINS
https://github.com/brentyi/egoallo
```

## 本地环境

`.envs/` 下的环境目录统一使用：

```text
<目标>-<基座>
```

当前 EC2 本地环境：

```text
.envs/sqrtVINS-docker
.envs/egoallo-uv
```

这些目录不会提交到 Git。它们可能包含机器相关脚本、缓存、生成文件、模型/数据路径或密钥。

### sqrtVINS

sqrtVINS 上游 README 的原生构建目标是 Ubuntu 20.04 + ROS1/catkin。对于 Ubuntu 24.04 宿主机，优先使用 Docker 或其他隔离的 ROS 环境，不建议直接把 ROS 装进宿主系统。

### EgoAllo

EgoAllo 要求 Python 3.12 或更高版本。当前 EC2 上使用 `uv` 在 `.envs/egoallo-uv` 下构建环境，依赖来源是：

```bash
third-parties/egoallo/pyproject.toml
```

上游 README 中推理相关的额外内容，例如 JAX CUDA、`jaxls`、checkpoint、示例轨迹和 SMPL-H 模型文件，应在真正需要时单独处理，不提交进本仓库。

不要提交 `.env` 等本地密钥文件。
