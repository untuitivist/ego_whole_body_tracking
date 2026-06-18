#!/usr/bin/env bash
set -euo pipefail

PROJECT_ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/../.." && pwd)"
SCRIPT_DIR="$PROJECT_ROOT/scripts/sqrtVINS"
DATA_NAME="20260508_050222_session1_random_10s"
DATA_DIR="$PROJECT_ROOT/datas/$DATA_NAME"
RESULT_DIR="$PROJECT_ROOT/results/$DATA_NAME/sqrtVINS"
BASE_IMAGE="ego-whole-body/sqrtvins:ros1-noetic"
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
if [[ ! -d "$PROJECT_ROOT/third-parties/sqrtVINS" ]]; then
  echo "missing sqrtVINS checkout: $PROJECT_ROOT/third-parties/sqrtVINS" >&2
  exit 1
fi

mkdir -p "$RESULT_DIR/logs"

echo "building runtime image $IMAGE_NAME from $BASE_IMAGE"
"${DOCKER_BIN[@]}" build \
  -t "$IMAGE_NAME" \
  -f "$SCRIPT_DIR/Dockerfile.runtime" \
  "$SCRIPT_DIR" \
  > "$RESULT_DIR/logs/docker_build_runtime.log" 2>&1

echo "running sqrtVINS benchmark for $DATA_NAME"
"${DOCKER_BIN[@]}" run --rm \
  -v "$PROJECT_ROOT:$CONTAINER_PROJECT" \
  -v "$PROJECT_ROOT/third-parties/sqrtVINS:$CONTAINER_WS/src/sqrtVINS" \
  -w "$CONTAINER_PROJECT" \
  "$IMAGE_NAME" \
  bash -lc "set -euo pipefail
    source /opt/ros/noetic/setup.bash
    cd $CONTAINER_WS
    catkin build > $CONTAINER_PROJECT/results/$DATA_NAME/sqrtVINS/logs/catkin_build.log 2>&1
    source devel/setup.bash
    cd $CONTAINER_PROJECT
    python3 scripts/sqrtVINS/make_robocap_bag.py \
      --data-dir datas/$DATA_NAME \
      --output-bag results/$DATA_NAME/sqrtVINS/robocap_segment1_stereo_imu.bag \
      --manifest results/$DATA_NAME/sqrtVINS/bag_manifest.json \
      > results/$DATA_NAME/sqrtVINS/logs/make_bag.log 2>&1
    roslaunch ov_srvins serial.launch \
      config:=euroc_mav \
      bag:=$CONTAINER_PROJECT/results/$DATA_NAME/sqrtVINS/robocap_segment1_stereo_imu.bag \
      bag_start:=0.0 \
      bag_durr:=-1 \
      dolivetraj:=false \
      path_est:=$CONTAINER_PROJECT/results/$DATA_NAME/sqrtVINS/traj_estimate.txt \
      path_time:=$CONTAINER_PROJECT/results/$DATA_NAME/sqrtVINS/traj_timing.txt \
      init_poses_log_file_path:=$CONTAINER_PROJECT/results/$DATA_NAME/sqrtVINS/init_window_poses.txt \
      init_metadata_log_file_path:=$CONTAINER_PROJECT/results/$DATA_NAME/sqrtVINS/init_window_timing.txt \
      > $CONTAINER_PROJECT/results/$DATA_NAME/sqrtVINS/logs/roslaunch_serial.log 2>&1
  "

cat > "$RESULT_DIR/README.md" <<EOF
# sqrtVINS result for $DATA_NAME

This run uses the upstream sqrtVINS ROS1 serial.launch path with config:=euroc_mav.
The local benchmark clip is adapted into a EuRoC-like ROS bag with:

- /cam0/image_raw from robocap_segment1_video_left_eye.mp4
- /cam1/image_raw from robocap_segment1_video_right_eye.mp4
- /imu0 from robocap_segment1_imu_left.db

Important caveat: the source benchmark is MP4 + SQLite, not native EuRoC. The generated bag is an adapter artifact for pipeline validation, and IMU scale factors are explicit parameters in the conversion script.
EOF
