"""Local webserver for metrics dashboard and video survey collection."""

from __future__ import annotations

import argparse
import json
import mimetypes
from dataclasses import dataclass, field
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
from typing import Any
from urllib.parse import parse_qs, unquote, urlsplit

from asimovbm.survey import design_payload
from asimovbm.survey.analysis import aggregate_video_scores
from asimovbm.survey.export import participants_csv_text, write_participants_csv
from asimovbm.survey.storage import SurveyStorageError, SurveyStore
from asimovbm.survey.video_manifest import (
    VideoManifestError,
    empty_video_manifest,
    load_video_manifest,
)

from .artifact_index import list_runs, load_run


@dataclass(frozen=True)
class WebConfig:
    artifact_root: Path = Path("artifacts/local-validation")
    survey_root: Path = Path("artifacts/survey")
    video_root: Path = Path("artifacts/survey/videos")
    study_id: str = "pilot"
    video_manifest_path: Path | None = None
    host: str = "127.0.0.1"
    port: int = 8765
    include_q5: bool = False
    include_go2: bool = False


@dataclass(frozen=True)
class WebResponse:
    status: int
    body: bytes
    content_type: str
    headers: dict[str, str] = field(default_factory=dict)


class WebApp:
    def __init__(self, config: WebConfig) -> None:
        self.config = config

    def handle_request(
        self,
        method: str,
        raw_path: str,
        body: bytes = b"",
    ) -> WebResponse:
        parsed = urlsplit(raw_path)
        path = parsed.path
        query = parse_qs(parsed.query)
        try:
            if method == "GET":
                return self._handle_get(path, query)
            if method == "POST":
                return self._handle_post(path, body)
        except (FileNotFoundError, KeyError, SurveyStorageError, VideoManifestError, ValueError) as exc:
            status = 404 if isinstance(exc, FileNotFoundError | KeyError) else 400
            return _json_response({"error": str(exc)}, status=status)
        return _json_response({"error": "method not allowed"}, status=405)

    def _handle_get(self, path: str, query: dict[str, list[str]]) -> WebResponse:
        if path in {"/", "/survey"}:
            return _static_response("index.html")
        if path.startswith("/static/"):
            return _static_response(unquote(path.removeprefix("/static/")))
        if path == "/api/runs":
            return _json_response({"runs": list_runs(self.config.artifact_root)})
        if path.startswith("/api/runs/"):
            run_id = unquote(path.removeprefix("/api/runs/"))
            return _json_response(load_run(self.config.artifact_root, run_id))
        if path == "/api/survey/design":
            return _json_response(
                design_payload(
                    include_q5=self.config.include_q5,
                    include_go2=self.config.include_go2,
                )
            )
        if path == "/api/survey/videos":
            group_id = _single_query(query, "group")
            manifest = self._video_manifest()
            return _json_response(
                {
                    "study_id": manifest.study_id,
                    "group_id": group_id,
                    "videos": [
                        video.to_dict() for video in manifest.videos_for_group(group_id)
                    ],
                }
            )
        if path == "/api/survey/analysis":
            store = self._store()
            return _json_response(
                {
                    "study_id": self.config.study_id,
                    "aggregate": aggregate_video_scores(store.responses()),
                }
            )
        if path == "/api/survey/participants.csv":
            store = self._store()
            write_participants_csv(store)
            return WebResponse(
                status=200,
                body=participants_csv_text(
                    store.participants(),
                    store.responses(),
                ).encode("utf-8"),
                content_type="text/csv; charset=utf-8",
                headers={
                    "Content-Disposition": 'attachment; filename="participants.csv"'
                },
            )
        if path.startswith("/videos/"):
            return _file_response(
                _safe_child(self.config.video_root, unquote(path.removeprefix("/videos/")))
            )
        return _json_response({"error": "not found"}, status=404)

    def _handle_post(self, path: str, body: bytes) -> WebResponse:
        payload = _decode_json(body)
        store = self._store()
        if path == "/api/survey/participants":
            group_id = str(payload.get("group_id", ""))
            manifest = self._video_manifest()
            videos = manifest.videos_for_group(group_id)
            record = store.start_participant(
                group_id=group_id,
                participant_id=payload.get("participant_id"),
                assigned_video_ids=tuple(video.video_id for video in videos),
                metadata=payload.get("metadata", {}),
            )
            return _json_response({"participant": record}, status=201)
        if path == "/api/survey/responses":
            record = store.append_response(
                payload,
                manifest=self._video_manifest(),
                include_q5=self.config.include_q5,
            )
            return _json_response({"response": record}, status=201)
        return _json_response({"error": "not found"}, status=404)

    def _store(self) -> SurveyStore:
        return SurveyStore(self.config.survey_root, self.config.study_id)

    def _video_manifest(self):
        if self.config.video_manifest_path is None:
            return empty_video_manifest(study_id=self.config.study_id)
        return load_video_manifest(
            self.config.video_manifest_path,
            video_root=self.config.video_root,
        )


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(prog="asimovbm-web")
    parser.add_argument("--artifact-root", type=Path, default=Path("artifacts/local-validation"))
    parser.add_argument("--survey-root", type=Path, default=Path("artifacts/survey"))
    parser.add_argument("--video-root", type=Path, default=Path("artifacts/survey/videos"))
    parser.add_argument("--video-manifest", type=Path)
    parser.add_argument("--study-id", default="pilot")
    parser.add_argument("--host", default="127.0.0.1")
    parser.add_argument("--port", type=int, default=8765)
    parser.add_argument("--include-q5", action="store_true")
    parser.add_argument("--include-go2", action="store_true")
    return parser


def main(argv: list[str] | None = None) -> int:
    args = build_parser().parse_args(argv)
    config = WebConfig(
        artifact_root=args.artifact_root,
        survey_root=args.survey_root,
        video_root=args.video_root,
        study_id=args.study_id,
        video_manifest_path=args.video_manifest,
        host=args.host,
        port=args.port,
        include_q5=args.include_q5,
        include_go2=args.include_go2,
    )
    if config.video_manifest_path is not None and not config.video_manifest_path.exists():
        raise SystemExit(f"video manifest does not exist: {config.video_manifest_path}")
    serve(config)
    return 0


def serve(config: WebConfig) -> None:
    app = WebApp(config)

    class Handler(BaseHTTPRequestHandler):
        def do_GET(self) -> None:  # noqa: N802
            self._send(app.handle_request("GET", self.path))

        def do_POST(self) -> None:  # noqa: N802
            length = int(self.headers.get("Content-Length") or 0)
            body = self.rfile.read(length) if length else b""
            self._send(app.handle_request("POST", self.path, body))

        def log_message(self, format: str, *args: Any) -> None:
            return

        def _send(self, response: WebResponse) -> None:
            self.send_response(response.status)
            self.send_header("Content-Type", response.content_type)
            self.send_header("Content-Length", str(len(response.body)))
            for name, value in response.headers.items():
                self.send_header(name, value)
            self.end_headers()
            self.wfile.write(response.body)

    server = ThreadingHTTPServer((config.host, config.port), Handler)
    print(f"asimovbm webserver: http://{config.host}:{config.port}")
    try:
        server.serve_forever()
    except KeyboardInterrupt:
        pass
    finally:
        server.server_close()


def _json_response(payload: dict[str, Any], *, status: int = 200) -> WebResponse:
    return WebResponse(
        status=status,
        body=(json.dumps(payload, sort_keys=True) + "\n").encode("utf-8"),
        content_type="application/json; charset=utf-8",
    )


def _static_response(name: str) -> WebResponse:
    if "/" in name or name.startswith("."):
        return _json_response({"error": "invalid static path"}, status=400)
    return _file_response(Path(__file__).with_name("static") / name)


def _file_response(path: Path) -> WebResponse:
    if not path.exists() or not path.is_file():
        raise FileNotFoundError(path.as_posix())
    content_type = mimetypes.guess_type(path.name)[0] or "application/octet-stream"
    return WebResponse(
        status=200,
        body=path.read_bytes(),
        content_type=content_type,
    )


def _decode_json(body: bytes) -> dict[str, Any]:
    try:
        payload = json.loads(body.decode("utf-8") or "{}")
    except json.JSONDecodeError as exc:
        raise ValueError("request body must be JSON") from exc
    if not isinstance(payload, dict):
        raise ValueError("request body must be a JSON object")
    return payload


def _single_query(query: dict[str, list[str]], name: str) -> str:
    values = query.get(name)
    if not values or values[0] == "":
        raise ValueError(f"missing query parameter: {name}")
    return values[0]


def _safe_child(root: Path, child: str | Path) -> Path:
    root_resolved = root.resolve()
    candidate = Path(child)
    if not candidate.is_absolute():
        candidate = root_resolved / candidate
    candidate_resolved = candidate.resolve(strict=False)
    if candidate_resolved != root_resolved and root_resolved not in candidate_resolved.parents:
        raise ValueError("path escapes configured root")
    return candidate_resolved


if __name__ == "__main__":
    raise SystemExit(main())
