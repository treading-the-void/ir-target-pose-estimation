"""Camera connection and capture, separate from image processing."""

import cv2

from .settings import CameraSettings


BACKENDS = {"any": cv2.CAP_ANY, "msmf": cv2.CAP_MSMF, "dshow": cv2.CAP_DSHOW}


def list_camera_names() -> list[str]:
    """Return Windows DirectShow names when pygrabber is installed."""
    try:
        from pygrabber.dshow_graph import FilterGraph
    except ImportError as exc:
        raise RuntimeError("Install pygrabber to select a Windows camera by name") from exc
    return FilterGraph().get_input_devices()


def resolve_camera_index(settings: CameraSettings) -> int:
    if not settings.device_name:
        return settings.index
    names = list_camera_names()
    query = settings.device_name.casefold()
    matches = [i for i, name in enumerate(names) if query in name.casefold()]
    if len(matches) != 1:
        raise RuntimeError(f"Expected one camera matching {settings.device_name!r}; found {matches}: {names}")
    return matches[0]


def open_camera(settings: CameraSettings) -> cv2.VideoCapture:
    backend = BACKENDS.get(settings.backend.lower())
    if backend is None:
        raise ValueError(f"Unknown camera backend: {settings.backend}")
    cap = cv2.VideoCapture(resolve_camera_index(settings), backend)
    if not cap.isOpened():
        cap.release()
        raise RuntimeError("Could not open infrared camera")
    cap.set(cv2.CAP_PROP_FRAME_WIDTH, settings.width)
    cap.set(cv2.CAP_PROP_FRAME_HEIGHT, settings.height)
    cap.set(cv2.CAP_PROP_FPS, settings.fps)
    if settings.exposure is not None:
        cap.set(cv2.CAP_PROP_EXPOSURE, settings.exposure)
    return cap

