# ego_whole_body_tracking

用于 ego whole-body tracking 实验和第三方运动跟踪基线的工作区。

## 目录结构

```text
ego_whole_body_tracking/
└── third-parties/
    └── sqrtVINS/              # rpng/sqrtVINS git submodule
```

本地环境统一放在 `.envs/` 下，但 `.envs/` 会被 Git 忽略。

## 第三方仓库

`sqrtVINS` 通过 Git submodule 管理：

```bash
git submodule update --init --recursive
```

当前 submodule 地址：

```text
https://github.com/rpng/sqrtVINS
```

## sqrtVINS 环境

当前服务器上使用本地 Docker/ROS1 Noetic 环境：

```text
.envs/sqrtVINS-docker
```

这个目录不会提交到 Git。原因是环境目录可能包含机器相关脚本、缓存、生成文件或密钥。

sqrtVINS 上游 README 的原生构建目标是 Ubuntu 20.04 + ROS1/catkin。对于 Ubuntu 24.04 宿主机，优先使用 Docker 或其他隔离的 ROS 环境，不建议直接把 ROS 装进宿主系统。

## 环境命名规则

`.envs/` 下的环境目录统一使用：

```text
<目标>-<基座>
```

例如：

```text
sqrtVINS-docker
egoAllo-uv
```

不要提交 `.env` 等本地密钥文件。
