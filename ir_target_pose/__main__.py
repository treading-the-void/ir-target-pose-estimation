"""Command line interface for camera calibration and target pose estimation."""

import argparse
import json
from pathlib import Path

import cv2
import numpy as np

from .calibration import calibrate_chessboard, save_calibration
from .camera import open_camera
from .pipeline import TargetPoseEstimator, annotate
from .settings import load_settings


def main() -> None:
    parser = argparse.ArgumentParser(description="Monocular infrared dot-board pose estimation")
    parser.add_argument("--config", default="configs/config.example.json", help="User settings JSON")
    commands = parser.add_subparsers(dest="command", required=True)
    capture = commands.add_parser("capture-calibration", help="Save chessboard images from the IR camera")
    capture.add_argument("--directory", default="captures")
    calibrate = commands.add_parser("calibrate", help="Calibrate from chessboard images")
    calibrate.add_argument("--images", required=True, help="Image glob, e.g. 'captures/*.png'")
    calibrate.add_argument("--columns", type=int, default=9, help="Inner corner columns")
    calibrate.add_argument("--rows", type=int, default=6, help="Inner corner rows")
    calibrate.add_argument("--square-mm", type=float, required=True)
    detect = commands.add_parser("detect", help="Estimate board pose in an image")
    detect.add_argument("--image", required=True)
    detect.add_argument("--output", help="Save annotated image")
    live = commands.add_parser("live", help="Estimate board poses from a camera")
    live.add_argument("--jsonl", help="Write poses as JSON lines")
    args = parser.parse_args()
    settings = load_settings(args.config)

    if args.command == "capture-calibration":
        directory = Path(args.directory)
        directory.mkdir(parents=True, exist_ok=True)
        cap = open_camera(settings.camera)
        count = len(list(directory.glob("chessboard_*.png")))
        try:
            while True:
                ok, frame = cap.read()
                if not ok:
                    raise RuntimeError("Camera frame read failed")
                cv2.imshow("Chessboard capture (space: save, q: quit)", frame)
                key = cv2.waitKey(1) & 0xFF
                if key == ord("q"):
                    break
                if key == ord(" "):
                    count += 1
                    path = directory / f"chessboard_{count:04d}.png"
                    encoded, data = cv2.imencode(".png", frame)
                    if not encoded:
                        raise OSError(f"Cannot save image: {path}")
                    path.write_bytes(data.tobytes())
                    print(path)
        finally:
            cap.release()
            cv2.destroyAllWindows()
        return

    if args.command == "calibrate":
        # pathlib.glob does not accept absolute globs on all supported Python versions.
        from glob import glob
        images = [Path(p) for p in sorted(glob(args.images))]
        rms, K, D, size, count = calibrate_chessboard(
            images, (args.columns, args.rows), args.square_mm)
        save_calibration(settings.calibration_file, K, D, size)
        print(json.dumps({"file": str(settings.calibration_file), "images_used": count,
                          "image_size": size, "rms_px": rms}, ensure_ascii=False))
        return

    estimator = TargetPoseEstimator(settings)
    if args.command == "detect":
        image_path = Path(args.image)
        raw = np.fromfile(image_path, dtype=np.uint8) if image_path.is_file() else np.empty(0, np.uint8)
        frame = cv2.imdecode(raw, cv2.IMREAD_UNCHANGED) if raw.size else None
        if frame is None:
            parser.error(f"Cannot read image: {args.image}")
        poses, _ = estimator.process(frame)
        print(json.dumps([pose.as_dict() for pose in poses], ensure_ascii=False, indent=2))
        if args.output:
            output = Path(args.output)
            output.parent.mkdir(parents=True, exist_ok=True)
            encoded, data = cv2.imencode(output.suffix or ".png",
                                        annotate(frame, poses, estimator.camera_matrix,
                                                 estimator.distortion, settings.detection,
                                                 board_colors=estimator.board_colors))
            if not encoded:
                raise OSError(f"Cannot save annotated image: {output}")
            output.write_bytes(data.tobytes())
        return

    cap = open_camera(settings.camera)
    if args.jsonl:
        Path(args.jsonl).parent.mkdir(parents=True, exist_ok=True)
    stream = open(args.jsonl, "w", encoding="utf-8") if args.jsonl else None
    try:
        while True:
            ok, frame = cap.read()
            if not ok:
                raise RuntimeError("Camera frame read failed")
            poses, _ = estimator.process(frame)
            if stream:
                stream.write(json.dumps([pose.as_dict() for pose in poses], ensure_ascii=False) + "\n")
                stream.flush()
            cv2.imshow("Infrared target pose (q to quit)",
                       annotate(frame, poses, estimator.camera_matrix,
                                estimator.distortion, settings.detection,
                                board_colors=estimator.board_colors))
            if cv2.waitKey(1) & 0xFF == ord("q"):
                break
    finally:
        cap.release()
        if stream:
            stream.close()
        cv2.destroyAllWindows()


if __name__ == "__main__":
    main()
