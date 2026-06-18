# ego_whole_body_tracking

用于 ego whole-body tracking 实验和第三方运动跟踪基线的工作区。

## 目录结构

```text
ego_whole_body_tracking/
├── workflow/                 # 项目级脚本和适配层
└── third-parties/
    ├── sqrtVINS/             # rpng/sqrtVINS git submodule
    ├── egoallo/              # brentyi/egoallo git submodule
    └── HaWoR/                # ThunderVVV/HaWoR git submodule
```

本地环境和 benchmark 片段分别放在 `.envs/` 与 `datas/` 下；两者都会被 Git 忽略。

## 第三方仓库

第三方基线通过 Git submodule 管理：

```bash
git submodule update --init --recursive
```

当前 submodule：

```text
https://github.com/rpng/sqrtVINS
https://github.com/brentyi/egoallo
https://github.com/ThunderVVV/HaWoR
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
.envs/hawor-uv
```

EgoAllo 和 HaWoR 默认不建议共用一个 Python 环境。EgoAllo 要求 Python 3.12+，当前安装 Torch 2.7.1；HaWoR README 目标是 Python 3.10、Torch 1.13.0 + CUDA 11.7、NumPy 1.26.4，并且包含若干 CUDA/C++ 扩展。除非后续做过兼容性验证，否则应保持环境隔离。

## 本地 benchmark 数据

benchmark 片段放在本地 `datas/` 下，并被 Git 忽略。当前 EC2 benchmark 数据：

```text
datas/20260508_050222_session1_random_10s
```

来源对应：

```text
Z:\DATASETS\Frodobots\robocap_lab\20260508_050222_session1_random_10s
```

不要提交 `.env`、模型 checkpoint 或数据集文件。
