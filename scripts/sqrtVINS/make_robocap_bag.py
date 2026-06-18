#!/usr/bin/env python3
from __future__ import annotations

import argparse
import json
import shutil
import sqlite3
import subprocess
from bisect import bisect_left
from pathlib import Path

import cv2
import rosbag
import rospy
from cv_bridge import CvBridge
from sensor_msgs.msg import Image, Imu


def ns_to_time(ns: int) -> rospy.Time:
    return rospy.Time(secs=ns // 1_000_000_000, nsecs=ns % 1_000_000_000)


def video_comment_ns(video_path: Path) -> int:
    if shutil.which("ffprobe") is None:
        raise RuntimeError("ffprobe is required to read the MP4 comment timestamp; install ffmpeg in the runtime image")
    data = json.loads(
        subprocess.run(
            [
                "ffprobe",
                "-v",
                "error",
                "-show_format",
                "-print_format",
                "json",
                str(video_path),
            ],
            check=True,
            text=True,
            capture_output=True,
        ).stdout
    )
    try:
        return int(data["format"]["tags"]["comment"]) * 1000
    except KeyError as exc:
        raise RuntimeError(f"missing MP4 comment timestamp in {video_path}") from exc


def write_video(bag: rosbag.Bag, video_path: Path, topic: str, frame_id: str, image_scale: float) -> dict:
    cap = cv2.VideoCapture(str(video_path))
    if not cap.isOpened():
        raise RuntimeError(f"failed to open video: {video_path}")
    fps = cap.get(cv2.CAP_PROP_FPS) or 30.0
    start_ns = video_comment_ns(video_path)
    bridge = CvBridge()
    count = 0
    first_ns = None
    last_ns = None
    while True:
        ok, frame_bgr = cap.read()
        if not ok:
            break
        if image_scale != 1.0:
            frame_bgr = cv2.resize(frame_bgr, None, fx=image_scale, fy=image_scale, interpolation=cv2.INTER_AREA)
        gray = cv2.cvtColor(frame_bgr, cv2.COLOR_BGR2GRAY)
        stamp_ns = start_ns + int(round(count * 1_000_000_000 / fps))
        msg: Image = bridge.cv2_to_imgmsg(gray, encoding="mono8")
        msg.header.stamp = ns_to_time(stamp_ns)
        msg.header.frame_id = frame_id
        bag.write(topic, msg, msg.header.stamp)
        first_ns = stamp_ns if first_ns is None else first_ns
        last_ns = stamp_ns
        count += 1
    cap.release()
    return {"path": str(video_path), "topic": topic, "frames": count, "fps": fps, "first_ns": first_ns, "last_ns": last_ns}


def read_rows(db_path: Path, table: str) -> list[tuple[int, float, float, float]]:
    with sqlite3.connect(db_path) as con:
        rows = con.execute(f"select timestamp, x, y, z from {table} order by timestamp").fetchall()
    return [(int(t), float(x), float(y), float(z)) for t, x, y, z in rows]


def nearest(rows: list[tuple[int, float, float, float]], row_times: list[int], ts: int) -> tuple[int, float, float, float]:
    idx = bisect_left(row_times, ts)
    if idx <= 0:
        return rows[0]
    if idx >= len(rows):
        return rows[-1]
    before = rows[idx - 1]
    after = rows[idx]
    return before if abs(before[0] - ts) <= abs(after[0] - ts) else after


def write_imu(bag: rosbag.Bag, db_path: Path, topic: str, frame_id: str, accel_scale: float, gyro_scale: float) -> dict:
    acc_rows = read_rows(db_path, "acc_data")
    gyro_rows = read_rows(db_path, "gyro_data")
    if not acc_rows or not gyro_rows:
        raise RuntimeError(f"missing acc_data or gyro_data rows in {db_path}")
    acc_times = [row[0] for row in acc_rows]
    count = 0
    for ts, gx, gy, gz in gyro_rows:
        _ats, ax, ay, az = nearest(acc_rows, acc_times, ts)
        msg = Imu()
        msg.header.stamp = ns_to_time(ts)
        msg.header.frame_id = frame_id
        msg.angular_velocity.x = gx * gyro_scale
        msg.angular_velocity.y = gy * gyro_scale
        msg.angular_velocity.z = gz * gyro_scale
        msg.linear_acceleration.x = ax * accel_scale
        msg.linear_acceleration.y = ay * accel_scale
        msg.linear_acceleration.z = az * accel_scale
        msg.orientation_covariance[0] = -1.0
        bag.write(topic, msg, msg.header.stamp)
        count += 1
    return {
        "path": str(db_path),
        "topic": topic,
        "messages": count,
        "first_ns": gyro_rows[0][0],
        "last_ns": gyro_rows[-1][0],
        "accel_scale": accel_scale,
        "gyro_scale": gyro_scale,
    }


def main() -> None:
    parser = argparse.ArgumentParser(description="Convert the local robocap benchmark clip to a EuRoC-like ROS1 bag for sqrtVINS.")
    parser.add_argument("--data-dir", type=Path, required=True)
    parser.add_argument("--output-bag", type=Path, required=True)
    parser.add_argument("--manifest", type=Path, required=True)
    parser.add_argument("--image-scale", type=float, default=0.5)
    parser.add_argument("--accel-scale", type=float, default=0.0015)
    parser.add_argument("--gyro-scale", type=float, default=0.001)
    args = parser.parse_args()

    args.output_bag.parent.mkdir(parents=True, exist_ok=True)
    args.manifest.parent.mkdir(parents=True, exist_ok=True)
    data_dir = args.data_dir
    left_eye = data_dir / "robocap_segment1_video_left_eye.mp4"
    right_eye = data_dir / "robocap_segment1_video_right_eye.mp4"
    imu_left = data_dir / "robocap_segment1_imu_left.db"
    for path in (left_eye, right_eye, imu_left):
        if not path.exists():
            raise FileNotFoundError(path)

    manifest = {"inputs": {}, "notes": []}
    manifest["notes"].append("Adapter-generated bag for sqrtVINS serial.launch; source is MP4+SQLite, not native EuRoC.")
    manifest["notes"].append("Video frame stamps use mp4 comment microseconds as capture start plus frame index / fps.")
    manifest["notes"].append("IMU units are scaled from raw integer columns with configurable accel_scale and gyro_scale.")

    with rosbag.Bag(str(args.output_bag), "w", compression="bz2") as bag:
        manifest["inputs"]["cam0"] = write_video(bag, left_eye, "/cam0/image_raw", "cam0", args.image_scale)
        manifest["inputs"]["cam1"] = write_video(bag, right_eye, "/cam1/image_raw", "cam1", args.image_scale)
        manifest["inputs"]["imu0"] = write_imu(bag, imu_left, "/imu0", "imu0", args.accel_scale, args.gyro_scale)

    manifest["output_bag"] = str(args.output_bag)
    args.manifest.write_text(json.dumps(manifest, indent=2), encoding="utf-8")
    print(json.dumps(manifest, indent=2))


if __name__ == "__main__":
    main()
