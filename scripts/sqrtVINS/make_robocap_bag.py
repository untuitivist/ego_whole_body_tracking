#!/usr/bin/env python3
from __future__ import annotations

import argparse
import json
import shutil
import sqlite3
import subprocess
from bisect import bisect_left
from pathlib import Path
from typing import Any

import cv2
import rosbag
import rospy
from cv_bridge import CvBridge
from sensor_msgs.msg import Image, Imu

HOMIES_GYRO_SCALE = 0.000266316
HOMIES_ACCEL_SCALE = 0.001197101


def ns_to_time(ns: int) -> rospy.Time:
    return rospy.Time(secs=ns // 1_000_000_000, nsecs=ns % 1_000_000_000)


def run_ffprobe(args: list[str]) -> str:
    if shutil.which("ffprobe") is None:
        raise RuntimeError("ffprobe is required; install ffmpeg in the runtime image")
    return subprocess.run(["ffprobe", *args], check=True, text=True, capture_output=True).stdout


def video_comment_ns(video_path: Path) -> int:
    data = json.loads(run_ffprobe(["-v", "error", "-show_format", "-print_format", "json", str(video_path)]))
    try:
        return int(data["format"]["tags"]["comment"]) * 1000
    except KeyError as exc:
        raise RuntimeError(f"missing MP4 comment timestamp in {video_path}") from exc


def video_time_base(video_path: Path) -> tuple[int, int] | None:
    out = run_ffprobe([
        "-v", "error", "-select_streams", "v:0",
        "-show_entries", "stream=time_base", "-of", "csv=p=0", str(video_path),
    ]).strip()
    if not out or "/" not in out:
        return None
    num, den = out.split("/", 1)
    den_i = int(den)
    return (int(num), den_i) if den_i > 0 else None


def frame_pts(video_path: Path) -> list[int]:
    for field in ("pkt_pts", "best_effort_timestamp", "pkt_dts"):
        out = run_ffprobe([
            "-v", "error", "-select_streams", "v:0",
            "-show_entries", f"frame={field}", "-of", "csv=p=0", str(video_path),
        ])
        pts: list[int] = []
        for line in out.splitlines():
            value = line.strip().split(",")[0]
            if not value or value == "N/A":
                continue
            try:
                pts.append(int(value))
            except ValueError:
                pass
        if pts:
            return pts
    return []


def video_stamp_ns(video_path: Path, frame_index: int, fps: float, pts: list[int], time_base: tuple[int, int] | None) -> int:
    start_ns = video_comment_ns(video_path)
    if pts and time_base and frame_index < len(pts):
        num, den = time_base
        return start_ns + (pts[frame_index] * num * 1_000_000_000 // den)
    return start_ns + int(round(frame_index * 1_000_000_000 / fps))


def video_range(video_path: Path) -> tuple[int, int, float, int]:
    cap = cv2.VideoCapture(str(video_path))
    if not cap.isOpened():
        raise RuntimeError(f"failed to open video: {video_path}")
    fps = cap.get(cv2.CAP_PROP_FPS) or 30.0
    frames = int(cap.get(cv2.CAP_PROP_FRAME_COUNT))
    cap.release()
    pts = frame_pts(video_path)
    tb = video_time_base(video_path)
    if frames <= 0:
        raise RuntimeError(f"no frames in video: {video_path}")
    return video_stamp_ns(video_path, 0, fps, pts, tb), video_stamp_ns(video_path, frames - 1, fps, pts, tb), fps, frames


def read_rows(db_path: Path, table: str) -> list[tuple[int, float, float, float]]:
    with sqlite3.connect(db_path) as con:
        rows = con.execute(f"select timestamp, x, y, z from {table} order by timestamp").fetchall()
    return [(int(t), float(x), float(y), float(z)) for t, x, y, z in rows]


def interpolate_acc(acc_rows: list[tuple[int, float, float, float]], acc_times: list[int], ts: int) -> tuple[float, float, float]:
    idx = bisect_left(acc_times, ts)
    if idx <= 0:
        return acc_rows[0][1], acc_rows[0][2], acc_rows[0][3]
    if idx >= len(acc_rows):
        return acc_rows[-1][1], acc_rows[-1][2], acc_rows[-1][3]
    t0, x0, y0, z0 = acc_rows[idx - 1]
    t1, x1, y1, z1 = acc_rows[idx]
    ratio = 0.0 if t1 == t0 else (ts - t0) / (t1 - t0)
    return x0 + ratio * (x1 - x0), y0 + ratio * (y1 - y0), z0 + ratio * (z1 - z0)


def imu_range(db_path: Path) -> tuple[int, int, int]:
    gyro_rows = read_rows(db_path, "gyro_data")
    if not gyro_rows:
        raise RuntimeError(f"missing gyro_data rows in {db_path}")
    return gyro_rows[0][0], gyro_rows[-1][0], len(gyro_rows)


def write_video(
    bag: rosbag.Bag,
    video_path: Path,
    topic: str,
    frame_id: str,
    image_scale: float,
    min_ns: int | None,
    max_ns: int | None,
) -> dict[str, Any]:
    cap = cv2.VideoCapture(str(video_path))
    if not cap.isOpened():
        raise RuntimeError(f"failed to open video: {video_path}")
    fps = cap.get(cv2.CAP_PROP_FPS) or 30.0
    pts = frame_pts(video_path)
    tb = video_time_base(video_path)
    bridge = CvBridge()
    decoded = 0
    written = 0
    first_ns = None
    last_ns = None
    while True:
        ok, frame_bgr = cap.read()
        if not ok:
            break
        stamp_ns = video_stamp_ns(video_path, decoded, fps, pts, tb)
        decoded += 1
        if min_ns is not None and stamp_ns < min_ns:
            continue
        if max_ns is not None and stamp_ns > max_ns:
            continue
        if image_scale != 1.0:
            frame_bgr = cv2.resize(frame_bgr, None, fx=image_scale, fy=image_scale, interpolation=cv2.INTER_AREA)
        gray = cv2.cvtColor(frame_bgr, cv2.COLOR_BGR2GRAY)
        msg: Image = bridge.cv2_to_imgmsg(gray, encoding="mono8")
        msg.header.stamp = ns_to_time(stamp_ns)
        msg.header.frame_id = frame_id
        bag.write(topic, msg, msg.header.stamp)
        first_ns = stamp_ns if first_ns is None else first_ns
        last_ns = stamp_ns
        written += 1
    cap.release()
    return {"path": str(video_path), "topic": topic, "decoded_frames": decoded, "written_frames": written, "fps": fps, "first_ns": first_ns, "last_ns": last_ns, "used_pts": bool(pts and tb)}


def write_imu(
    bag: rosbag.Bag,
    db_path: Path,
    topic: str,
    frame_id: str,
    accel_scale: float,
    gyro_scale: float,
    min_ns: int | None,
    max_ns: int | None,
) -> dict[str, Any]:
    acc_rows = read_rows(db_path, "acc_data")
    gyro_rows = read_rows(db_path, "gyro_data")
    if not acc_rows or not gyro_rows:
        raise RuntimeError(f"missing acc_data or gyro_data rows in {db_path}")
    acc_times = [row[0] for row in acc_rows]
    written = 0
    first_ns = None
    last_ns = None
    last_written_ns = -1
    for ts, gx, gy, gz in gyro_rows:
        if ts <= last_written_ns:
            continue
        if min_ns is not None and ts < min_ns:
            continue
        if max_ns is not None and ts > max_ns:
            continue
        ax, ay, az = interpolate_acc(acc_rows, acc_times, ts)
        msg = Imu()
        msg.header.stamp = ns_to_time(ts)
        msg.header.frame_id = frame_id
        msg.angular_velocity.x = gx * gyro_scale
        msg.angular_velocity.y = gy * gyro_scale
        msg.angular_velocity.z = gz * gyro_scale
        msg.linear_acceleration.x = ax * accel_scale
        msg.linear_acceleration.y = ay * accel_scale
        msg.linear_acceleration.z = az * accel_scale
        msg.orientation.w = 1.0
        msg.orientation_covariance[0] = -1.0
        bag.write(topic, msg, msg.header.stamp)
        first_ns = ts if first_ns is None else first_ns
        last_ns = ts
        last_written_ns = ts
        written += 1
    return {"path": str(db_path), "topic": topic, "raw_gyro_rows": len(gyro_rows), "written_messages": written, "first_ns": first_ns, "last_ns": last_ns, "accel_scale": accel_scale, "gyro_scale": gyro_scale}


def load_alias_manifest(path: Path, profile_name: str | None) -> tuple[dict[str, Any], dict[str, Any]]:
    manifest = json.loads(path.read_text(encoding="utf-8"))
    active = profile_name or manifest.get("active_profile")
    if not active:
        raise RuntimeError("alias manifest has no active_profile")
    try:
        return manifest, manifest["profiles"][active]
    except KeyError as exc:
        raise RuntimeError(f"missing alias profile: {active}") from exc


def main() -> None:
    parser = argparse.ArgumentParser(description="Convert the local robocap benchmark clip to a ROS1 bag for sqrtVINS.")
    parser.add_argument("--data-dir", type=Path, required=True)
    parser.add_argument("--output-bag", type=Path, required=True)
    parser.add_argument("--manifest", type=Path, required=True)
    parser.add_argument("--alias-manifest", type=Path)
    parser.add_argument("--alias-profile")
    parser.add_argument("--image-scale", type=float, default=1.0)
    parser.add_argument("--accel-scale", type=float, default=HOMIES_ACCEL_SCALE)
    parser.add_argument("--gyro-scale", type=float, default=HOMIES_GYRO_SCALE)
    parser.add_argument("--no-align-intersection", action="store_true")
    args = parser.parse_args()

    args.output_bag.parent.mkdir(parents=True, exist_ok=True)
    args.manifest.parent.mkdir(parents=True, exist_ok=True)

    if args.alias_manifest:
        alias_manifest, profile = load_alias_manifest(args.alias_manifest, args.alias_profile)
        videos = profile.get("videos", [])
        imus = profile.get("imus", [])
    else:
        alias_manifest = None
        videos = [
            {"role": "left_eye", "source_path": "robocap_segment1_video_left_eye.mp4", "topic": "/cam0/image_raw", "frame_id": "cam0"},
            {"role": "right_eye", "source_path": "robocap_segment1_video_right_eye.mp4", "topic": "/cam1/image_raw", "frame_id": "cam1"},
        ]
        imus = [{"role": "left_imu", "source_path": "robocap_segment1_imu_left.db", "topic": "/imu0", "frame_id": "imu0"}]

    ranges: list[tuple[int, int]] = []
    for video in videos:
        path = args.data_dir / video["source_path"]
        if not path.exists():
            raise FileNotFoundError(path)
        start, end, _fps, _frames = video_range(path)
        ranges.append((start, end))
    for imu in imus:
        path = args.data_dir / imu["source_path"]
        if not path.exists():
            raise FileNotFoundError(path)
        start, end, _rows = imu_range(path)
        ranges.append((start, end))

    min_ns = max(start for start, _end in ranges) if ranges and not args.no_align_intersection else None
    max_ns = min(end for _start, end in ranges) if ranges and not args.no_align_intersection else None

    output: dict[str, Any] = {
        "alias_manifest": str(args.alias_manifest) if args.alias_manifest else None,
        "alias_profile": args.alias_profile or (alias_manifest or {}).get("active_profile"),
        "inputs": {"videos": [], "imus": []},
        "aligned_range_ns": {"start": min_ns, "end": max_ns, "duration_s": ((max_ns - min_ns) / 1e9 if min_ns and max_ns else None)},
        "notes": [
            "Generated by scripts/sqrtVINS/make_robocap_bag.py.",
            "Homies-style mode uses MP4 comment start timestamps plus frame PTS when available.",
            "IMU accelerometer samples are linearly interpolated to gyroscope timestamps.",
        ],
    }
    if alias_manifest:
        output["source_alias_notes"] = alias_manifest.get("notes", [])

    with rosbag.Bag(str(args.output_bag), "w", compression="bz2") as bag:
        for video in videos:
            output["inputs"]["videos"].append(write_video(
                bag,
                args.data_dir / video["source_path"],
                video["topic"],
                video.get("frame_id", video["topic"].strip("/").replace("/image_raw", "")),
                args.image_scale,
                min_ns,
                max_ns,
            ))
        for imu in imus:
            output["inputs"]["imus"].append(write_imu(
                bag,
                args.data_dir / imu["source_path"],
                imu["topic"],
                imu.get("frame_id", "imu0"),
                args.accel_scale,
                args.gyro_scale,
                min_ns,
                max_ns,
            ))

    output["output_bag"] = str(args.output_bag)
    args.manifest.write_text(json.dumps(output, indent=2), encoding="utf-8")
    print(json.dumps(output, indent=2))


if __name__ == "__main__":
    main()
