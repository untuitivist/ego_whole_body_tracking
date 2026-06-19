#!/usr/bin/env python3
import argparse
import json
from pathlib import Path


def relink(src: Path, dst: Path) -> None:
    src_resolved = src.resolve()
    if dst.is_symlink():
        current = dst.resolve(strict=False)
        if current == src_resolved:
            return
        raise FileExistsError(f"refusing to replace existing symlink {dst} -> {current}; expected {src_resolved}")
    if dst.exists():
        raise FileExistsError(f"refusing to replace existing path: {dst}")
    dst.symlink_to(src_resolved)


def main() -> None:
    parser = argparse.ArgumentParser(description="Create a Homies-named symlink view over a local robocap data directory.")
    parser.add_argument("--data-dir", required=True, type=Path)
    parser.add_argument("--alias-manifest", required=True, type=Path)
    parser.add_argument("--alias-profile", default=None)
    parser.add_argument("--output-dir", required=True, type=Path)
    args = parser.parse_args()

    manifest = json.loads(args.alias_manifest.read_text())
    profile_name = args.alias_profile or manifest.get("active_profile")
    profile = manifest["profiles"][profile_name]
    data_dir = args.data_dir.resolve()
    output_dir = args.output_dir.resolve()
    output_dir.mkdir(parents=True, exist_ok=True)

    links = []
    for video in profile.get("videos", []):
        src = data_dir / video["source_path"]
        dst = output_dir / video["homies_alias"]
        if not src.exists():
            raise FileNotFoundError(src)
        relink(src, dst)
        links.append({"kind": "video", "role": video.get("role"), "source": str(src), "link": str(dst)})

    for imu in profile.get("imus", []):
        src = data_dir / imu["source_path"]
        dst = output_dir / imu["homies_alias"]
        if not src.exists():
            raise FileNotFoundError(src)
        relink(src, dst)
        links.append({"kind": "imu", "role": imu.get("role"), "source": str(src), "link": str(dst)})

    view_manifest = {
        "schema_version": 1,
        "source_manifest": str(args.alias_manifest),
        "alias_profile": profile_name,
        "source_data_dir": str(data_dir),
        "homies_view_dir": str(output_dir),
        "links": links,
        "note": "Symlink-only view; no source data files are copied or renamed.",
    }
    (output_dir / "homies_view_manifest.json").write_text(json.dumps(view_manifest, indent=2) + "\n")
    print(json.dumps(view_manifest, indent=2))


if __name__ == "__main__":
    main()
