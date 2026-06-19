#!/usr/bin/env bash
set -euo pipefail

PROJECT_ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/../.." && pwd)"
SCRIPT_DIR="$PROJECT_ROOT/scripts/sqrtVINS"
DATA_NAME="20260508_050222_session1_random_10s"
DATA_DIR="$PROJECT_ROOT/datas/$DATA_NAME"
RESULT_DIR="$PROJECT_ROOT/results/$DATA_NAME/sqrtVINS/homies_front_alias"
BASE_IMAGE="ego-whole-body/sqrtvins:ros1-noetic"
IMAGE_NAME="ego-whole-body/sqrtvins:ros1-noetic-benchmark"
CONTAINER_WS="/workspace/sqrt_vins_ws"
CONTAINER_PROJECT="/workspace/ego_whole_body_tracking"
BAG_PATH="$RESULT_DIR/robocap_homies_front_alias.bag"
RUNTIME_CONFIG_DIR="$RESULT_DIR/runtime_config"

if docker ps >/dev/null 2>&1; then
  DOCKER_BIN=(docker)
else
  DOCKER_BIN=(sudo docker)
fi

if [[ ! -d "$DATA_DIR" ]]; then
  echo "missing benchmark data directory: $DATA_DIR" >&2
  exit 1
fi
if [[ ! -d "$PROJECT_ROOT/third-parties/sqrtVINS" ]]; then
  echo "missing sqrtVINS checkout: $PROJECT_ROOT/third-parties/sqrtVINS" >&2
  exit 1
fi

mkdir -p "$RESULT_DIR/logs" "$RUNTIME_CONFIG_DIR"
cp "$PROJECT_ROOT/third-parties/sqrtVINS/config/euroc_mav/estimator_config.yaml" "$RUNTIME_CONFIG_DIR/estimator_config.yaml"
cp "$PROJECT_ROOT/third-parties/sqrtVINS/config/euroc_mav/kalibr_imucam_chain.yaml" "$RUNTIME_CONFIG_DIR/kalibr_imucam_chain.yaml"
cp "$PROJECT_ROOT/third-parties/sqrtVINS/config/euroc_mav/kalibr_imu_chain.yaml" "$RUNTIME_CONFIG_DIR/kalibr_imu_chain.yaml"
python3 - "$RUNTIME_CONFIG_DIR/kalibr_imucam_chain.yaml" "$RUNTIME_CONFIG_DIR/kalibr_imu_chain.yaml" <<'PY'
from pathlib import Path
import sys
imucam = Path(sys.argv[1])
imu = Path(sys.argv[2])
text = imucam.read_text()
text = text.replace('/cam0/image_raw', '/cam1_left_front/image_raw')
text = text.replace('/cam1/image_raw', '/cam5_right_front/image_raw')
imucam.write_text(text)
text = imu.read_text().replace('/imu0', '/imu_mid_0')
imu.write_text(text)
PY

echo "building runtime image $IMAGE_NAME from $BASE_IMAGE"
"${DOCKER_BIN[@]}" build \
  -t "$IMAGE_NAME" \
  -f "$SCRIPT_DIR/Dockerfile.runtime" \
  "$SCRIPT_DIR" \
  > "$RESULT_DIR/logs/docker_build_runtime.log" 2>&1

echo "running Homies-style sqrtVINS alias benchmark for $DATA_NAME"
"${DOCKER_BIN[@]}" run --rm \
  -v "$PROJECT_ROOT:$CONTAINER_PROJECT" \
  -v "$PROJECT_ROOT/third-parties/sqrtVINS:$CONTAINER_WS/src/sqrtVINS" \
  -w "$CONTAINER_PROJECT" \
  "$IMAGE_NAME" \
  bash -lc "set -euo pipefail
    source /opt/ros/noetic/setup.bash
    cd $CONTAINER_WS
    catkin build > $CONTAINER_PROJECT/results/$DATA_NAME/sqrtVINS/homies_front_alias/logs/catkin_build.log 2>&1
    source devel/setup.bash
    cd $CONTAINER_PROJECT
    python3 scripts/sqrtVINS/make_robocap_bag.py \
      --data-dir datas/$DATA_NAME \
      --alias-manifest scripts/sqrtVINS/alias_manifest.json \
      --alias-profile front_stereo_dev0 \
      --output-bag results/$DATA_NAME/sqrtVINS/homies_front_alias/robocap_homies_front_alias.bag \
      --manifest results/$DATA_NAME/sqrtVINS/homies_front_alias/bag_manifest.json \
      > results/$DATA_NAME/sqrtVINS/homies_front_alias/logs/make_bag.log 2>&1
    roslaunch ov_srvins serial.launch \
      config_path:=$CONTAINER_PROJECT/results/$DATA_NAME/sqrtVINS/homies_front_alias/runtime_config/estimator_config.yaml \
      bag:=$CONTAINER_PROJECT/results/$DATA_NAME/sqrtVINS/homies_front_alias/robocap_homies_front_alias.bag \
      bag_start:=5.0 \
      bag_durr:=-1 \
      use_stereo:=true \
      max_cameras:=2 \
      do_bg:=true \
      win_time:=1.0 \
      dolivetraj:=false \
      path_est:=$CONTAINER_PROJECT/results/$DATA_NAME/sqrtVINS/homies_front_alias/traj_estimate.txt \
      path_time:=$CONTAINER_PROJECT/results/$DATA_NAME/sqrtVINS/homies_front_alias/traj_timing.txt \
      init_poses_log_file_path:=$CONTAINER_PROJECT/results/$DATA_NAME/sqrtVINS/homies_front_alias/init_window_poses.txt \
      init_metadata_log_file_path:=$CONTAINER_PROJECT/results/$DATA_NAME/sqrtVINS/homies_front_alias/init_window_timing.txt \
      > $CONTAINER_PROJECT/results/$DATA_NAME/sqrtVINS/homies_front_alias/logs/roslaunch_serial.log 2>&1 || true
  "

cat > "$RESULT_DIR/README.md" <<EOF
# Homies-style sqrtVINS alias result for $DATA_NAME

This run uses the local data directory directly and applies the alias map in scripts/sqrtVINS/alias_manifest.json.

Homies-style choices:
- left-front + right-front cameras
- dev0 primary IMU, aliased to robocap_segment1_imu_left.db because this benchmark has no middle IMU DB
- MP4 comment timestamp + frame PTS when available
- Homies IMU scales: gyro 0.000266316 rad/s/count, accel 0.001197101 m/s^2/count
- sqrtVINS args: bag_start=5, win_time=1, do_bg=true

The runtime config only patches topic names on the upstream euroc_mav template. It does not include S3 device calibration.
EOF
