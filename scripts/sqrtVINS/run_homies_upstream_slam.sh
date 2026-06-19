#!/usr/bin/env bash
set -euo pipefail

PROJECT_ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/../.." && pwd)"
SCRIPT_DIR="$PROJECT_ROOT/scripts/sqrtVINS"
HOMIES_DIR="$PROJECT_ROOT/third-parties/Project-Homies-Face-Blurring"
DATA_NAME="${DATA_NAME:-20260508_050222_session1_random_10s}"
PROFILE="${ALIAS_PROFILE:-front_stereo_dev0}"
DATA_DIR="$PROJECT_ROOT/datas/$DATA_NAME"
VIEW_DIR="$PROJECT_ROOT/work/homies_session_views/${DATA_NAME}_${PROFILE}"
RESULT_DIR="$PROJECT_ROOT/results/$DATA_NAME/sqrtVINS/homies_upstream_wrapper"
RUNTIME_CONFIG_DIR="$RESULT_DIR/runtime_config"
IMAGE_NAME="ego-whole-body/sqrtvins:ros1-noetic-benchmark"
CONTAINER_WS="/workspace/sqrt_vins_ws"
CONTAINER_PROJECT="/workspace/ego_whole_body_tracking"

if docker ps >/dev/null 2>&1; then
  DOCKER_BIN=(docker)
else
  DOCKER_BIN=(sudo docker)
fi

if [[ ! -d "$DATA_DIR" ]]; then
  echo "missing benchmark data directory: $DATA_DIR" >&2
  exit 1
fi
if [[ ! -d "$HOMIES_DIR/src/localization" ]]; then
  echo "missing Homies localization directory: $HOMIES_DIR/src/localization" >&2
  exit 1
fi
if [[ ! -d "$PROJECT_ROOT/third-parties/sqrtVINS" ]]; then
  echo "missing sqrtVINS checkout: $PROJECT_ROOT/third-parties/sqrtVINS" >&2
  exit 1
fi

mkdir -p "$RESULT_DIR/logs" "$RUNTIME_CONFIG_DIR" "$VIEW_DIR"
python3 "$SCRIPT_DIR/prepare_homies_session_view.py" \
  --data-dir "$DATA_DIR" \
  --alias-manifest "$SCRIPT_DIR/alias_manifest.json" \
  --alias-profile "$PROFILE" \
  --output-dir "$VIEW_DIR" \
  > "$RESULT_DIR/homies_view_manifest.json"

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

"${DOCKER_BIN[@]}" build \
  -t "$IMAGE_NAME" \
  -f "$SCRIPT_DIR/Dockerfile.runtime" \
  "$SCRIPT_DIR" \
  > "$RESULT_DIR/logs/docker_build_runtime.log" 2>&1

"${DOCKER_BIN[@]}" run --rm \
  -v "$PROJECT_ROOT:$CONTAINER_PROJECT" \
  -v "$PROJECT_ROOT:$PROJECT_ROOT" \
  -v "$PROJECT_ROOT/third-parties/sqrtVINS:$CONTAINER_WS/src/sqrtVINS" \
  -w "$CONTAINER_PROJECT" \
  "$IMAGE_NAME" \
  bash -lc "set -euo pipefail
    source /opt/ros/noetic/setup.bash
    cd $CONTAINER_WS
    catkin build > $CONTAINER_PROJECT/results/$DATA_NAME/sqrtVINS/homies_upstream_wrapper/logs/catkin_build.log 2>&1
    source devel/setup.bash
    cd $CONTAINER_PROJECT/third-parties/Project-Homies-Face-Blurring/src/localization
    python3 create_rosbag_from_db.py \
      $PROJECT_ROOT/work/homies_session_views/${DATA_NAME}_${PROFILE} \
      --cameras left-front right-front \
      --imus 0 \
      --segment 1 \
      --imu_rate_src 200 \
      --video_rate 30 \
      --output $CONTAINER_PROJECT/results/$DATA_NAME/sqrtVINS/homies_upstream_wrapper/homies_upstream_output.bag \
      > $CONTAINER_PROJECT/results/$DATA_NAME/sqrtVINS/homies_upstream_wrapper/logs/homies_create_rosbag.log 2>&1
    roslaunch ov_srvins serial.launch \
      config_path:=$CONTAINER_PROJECT/results/$DATA_NAME/sqrtVINS/homies_upstream_wrapper/runtime_config/estimator_config.yaml \
      bag:=$CONTAINER_PROJECT/results/$DATA_NAME/sqrtVINS/homies_upstream_wrapper/homies_upstream_output.bag \
      bag_start:=5.0 \
      bag_durr:=-1 \
      use_stereo:=true \
      max_cameras:=2 \
      do_bg:=true \
      win_time:=1.0 \
      dolivetraj:=false \
      path_est:=$CONTAINER_PROJECT/results/$DATA_NAME/sqrtVINS/homies_upstream_wrapper/traj_estimate.txt \
      path_time:=$CONTAINER_PROJECT/results/$DATA_NAME/sqrtVINS/homies_upstream_wrapper/traj_timing.txt \
      init_poses_log_file_path:=$CONTAINER_PROJECT/results/$DATA_NAME/sqrtVINS/homies_upstream_wrapper/init_window_poses.txt \
      init_metadata_log_file_path:=$CONTAINER_PROJECT/results/$DATA_NAME/sqrtVINS/homies_upstream_wrapper/init_window_timing.txt \
      > $CONTAINER_PROJECT/results/$DATA_NAME/sqrtVINS/homies_upstream_wrapper/logs/roslaunch_serial.log 2>&1 || true
  "

cat > "$RESULT_DIR/README.md" <<EOF
# Homies upstream-wrapper sqrtVINS result for $DATA_NAME

This run creates a symlink-only Homies session view under work/homies_session_views and calls Homies' own src/localization/create_rosbag_from_db.py.

It does not modify third-parties/Project-Homies-Face-Blurring and does not copy or rename files under datas/.

Homies-compatible inputs:
- video_dev1_session1_segment1_left-front.mp4 -> datas/$DATA_NAME/robocap_segment1_video_left_front.mp4
- video_dev5_session1_segment1_right-front.mp4 -> datas/$DATA_NAME/robocap_segment1_video_right_front.mp4
- IMUWriter_dev0_session1_segment1.db -> datas/$DATA_NAME/robocap_segment1_imu_left.db

The SLAM launch uses Homies' default sqrtVINS arguments: left-front/right-front, IMU dev0, imu_rate_src=200, video_rate=30, bag_start=5, win_time=1, do_bg=true. Runtime camera/IMU config is still the local euroc_mav-derived placeholder with topic patches, not S3 device calibration.
EOF
