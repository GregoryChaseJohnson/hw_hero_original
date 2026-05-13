import os
import sys
from flask import Flask, render_template, jsonify, request, session, send_file, url_for, send_from_directory
import json
import importlib
import copy
import uuid
import io
import socket
from datetime import datetime, timezone, timedelta
from werkzeug.utils import secure_filename
from dotenv import load_dotenv
from itsdangerous import URLSafeSerializer, BadSignature
import qrcode

# Make sure Python can find your modules (assuming they're in the same directory or a subfolder)
sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))

APP_DIR = os.path.dirname(__file__)
RUN_DIR = os.path.abspath(os.path.join(APP_DIR, ".."))
PROJECT_ENV = os.path.join(RUN_DIR, ".env")
OUTPUT_JSON_PATH = os.path.join(APP_DIR, "output.json")
SENTENCE_MAPPING_PATH = os.path.join(RUN_DIR, "sentence_mapping.json")
SAVED_WRITINGS_PATH = os.path.join(RUN_DIR, "saved_writings.json")
MOBILE_UPLOADS_PATH = os.path.join(RUN_DIR, "mobile_uploads.json")
UPLOAD_DIR = os.path.join(RUN_DIR, "uploads")
ALLOWED_IMAGE_EXTENSIONS = {".jpg", ".jpeg", ".png", ".webp"}
MOBILE_UPLOAD_SESSION_ACTIVE_SECONDS = 45

load_dotenv(PROJECT_ENV)

try:
    from .correction_service import get_correction_explanation
    from .generate_explanation import generate_correction_explanation_single
except ImportError:
    from correction_service import get_correction_explanation
    from generate_explanation import generate_correction_explanation_single

app = Flask(__name__)
app.secret_key = (
    os.getenv("FLASK_SECRET_KEY")
    or os.getenv("SECRET_KEY")
    or "dev-insecure-change-me"
)

AUTH_USERS = {
    "Cheayoon Park": os.getenv("CHEAYOON_PARK_PASSWORD", "19910319"),
    "Chase Johnson": os.getenv("CHASE_JOHNSON_PASSWORD", "19841001"),
}
LEGACY_SAVED_WRITINGS_USER = "Chase Johnson"


def _session_user():
    user = session.get("authenticated_user")
    return user if user in AUTH_USERS else None


def _require_authenticated_user():
    user = _session_user()
    if not user:
        return jsonify({"error": "Authentication required"}), 401
    return None


def _mobile_upload_serializer():
    return URLSafeSerializer(app.secret_key, salt="mobile-upload")


def _build_mobile_upload_token(user):
    return _mobile_upload_serializer().dumps({"user": user})


def _load_mobile_upload_token(token):
    try:
        payload = _mobile_upload_serializer().loads(token)
    except BadSignature:
        return None
    user = (payload or {}).get("user")
    return user if user in AUTH_USERS else None


def _detect_lan_ip():
    sock = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
    try:
        sock.connect(("8.8.8.8", 80))
        return sock.getsockname()[0]
    except OSError:
        return "127.0.0.1"
    finally:
        sock.close()


def _mobile_upload_base_url():
    configured_base = (os.getenv("APP_PUBLIC_BASE_URL") or "").strip().rstrip("/")
    if configured_base:
        return configured_base

    host = (request.host or "").strip()
    if not host:
        return f"http://{_detect_lan_ip()}:5000"

    host_only, sep, port = host.partition(":")
    if host_only in {"127.0.0.1", "localhost"}:
        resolved_port = port or "5000"
        return f"http://{_detect_lan_ip()}:{resolved_port}"

    return f"{request.scheme}://{host}"


def _load_json_file(path, default):
    try:
        with open(path, "r", encoding="utf-8") as f:
            return json.load(f)
    except FileNotFoundError:
        return default


def _save_json_file(path, payload):
    with open(path, "w", encoding="utf-8") as f:
        json.dump(payload, f, indent=4, ensure_ascii=False)


def _load_mobile_uploads_payload():
    data = _load_json_file(MOBILE_UPLOADS_PATH, {"users": {}})
    if not isinstance(data, dict):
        return {"users": {}}
    users = data.get("users", {})
    normalized_users = {}
    if isinstance(users, dict):
        for user, record in users.items():
            normalized_users[user] = record if isinstance(record, dict) else {}
    return {"users": normalized_users}


def _parse_mobile_upload_timestamp(value):
    if not isinstance(value, str) or not value:
        return None
    try:
        parsed = datetime.fromisoformat(value)
    except ValueError:
        return None
    if parsed.tzinfo is None:
        return parsed.replace(tzinfo=timezone.utc)
    return parsed.astimezone(timezone.utc)


def _mobile_upload_record_is_active(record, now=None):
    if not isinstance(record, dict):
        return False
    last_seen_at = _parse_mobile_upload_timestamp(record.get("last_seen_at"))
    if not last_seen_at:
        return False
    now = now or datetime.now(timezone.utc)
    return (now - last_seen_at) < timedelta(seconds=MOBILE_UPLOAD_SESSION_ACTIVE_SECONDS)


def _cleanup_stale_mobile_upload_sessions(payload, now=None):
    if not isinstance(payload, dict):
        return False
    users = payload.get("users")
    if not isinstance(users, dict):
        payload["users"] = {}
        return False

    now = now or datetime.now(timezone.utc)
    changed = False
    for user, record in list(users.items()):
        if _mobile_upload_record_is_active(record, now=now):
            continue
        if isinstance(record, dict):
            _delete_uploaded_file_if_present(record.get("stored_filename"))
        users.pop(user, None)
        changed = True
    return changed


def _load_mobile_uploads_payload_clean():
    payload = _load_mobile_uploads_payload()
    if _cleanup_stale_mobile_upload_sessions(payload):
        _save_json_file(MOBILE_UPLOADS_PATH, payload)
    return payload


def _get_pending_mobile_upload(user):
    payload = _load_mobile_uploads_payload_clean()
    record = payload["users"].get(user)
    return record if isinstance(record, dict) else None


def _set_pending_mobile_upload(user, record):
    payload = _load_mobile_uploads_payload_clean()
    payload["users"][user] = record
    _save_json_file(MOBILE_UPLOADS_PATH, payload)


def _clear_pending_mobile_upload(user):
    payload = _load_mobile_uploads_payload_clean()
    record = payload["users"].pop(user, None)
    _save_json_file(MOBILE_UPLOADS_PATH, payload)
    return record


def _delete_uploaded_file_if_present(stored_filename):
    if not stored_filename:
        return
    image_path = os.path.join(UPLOAD_DIR, stored_filename)
    if os.path.exists(image_path):
        try:
            os.remove(image_path)
        except OSError:
            pass


def _build_writing_title(text, word_limit=4):
    words = (text or "").split()
    return " ".join(words[:word_limit]) or "Untitled writing"


def _derive_text_from_sentence_mapping(sentence_mapping, field_name):
    sentences = (sentence_mapping or {}).get("sentences", [])
    if not isinstance(sentences, list):
        return ""
    parts = [
        (item or {}).get(field_name, "").strip()
        for item in sentences
        if isinstance(item, dict) and (item or {}).get(field_name, "").strip()
    ]
    return " ".join(parts)


def _normalize_writing_text(text):
    return " ".join((text or "").split())


def _normalize_saved_writings_payload(data):
    if not isinstance(data, dict):
        return {"users": {user: {"writings": []} for user in AUTH_USERS}}

    users_payload = data.get("users")
    if isinstance(users_payload, dict):
        normalized_users = {}
        for user in AUTH_USERS:
            user_payload = users_payload.get(user, {})
            writings = user_payload.get("writings", []) if isinstance(user_payload, dict) else []
            normalized_users[user] = {
                "writings": writings if isinstance(writings, list) else []
            }
        return {"users": normalized_users}

    legacy_writings = data.get("writings", [])
    normalized_users = {user: {"writings": []} for user in AUTH_USERS}
    if isinstance(legacy_writings, list):
        normalized_users[LEGACY_SAVED_WRITINGS_USER]["writings"] = legacy_writings
    return {"users": normalized_users}


def _dedupe_saved_writings(writings):
    if not isinstance(writings, list):
        return []
    deduped = []
    seen_texts = set()
    for item in writings:
        normalized_text = _normalize_writing_text(item.get("submitted_text", ""))
        if normalized_text in seen_texts:
            continue
        seen_texts.add(normalized_text)
        deduped.append(item)
    return deduped


def _load_saved_writings(user):
    raw_payload = _load_json_file(SAVED_WRITINGS_PATH, {"users": {}})
    normalized_payload = _normalize_saved_writings_payload(raw_payload)
    user_payload = normalized_payload["users"].get(user, {"writings": []})
    writings = _dedupe_saved_writings(user_payload.get("writings", []))
    needs_save = raw_payload != normalized_payload
    if writings != user_payload.get("writings", []):
        normalized_payload["users"][user] = {"writings": writings}
        needs_save = True
    if needs_save:
        _save_json_file(SAVED_WRITINGS_PATH, normalized_payload)
    return writings


def _save_saved_writings(user, writings):
    normalized_payload = _normalize_saved_writings_payload(
        _load_json_file(SAVED_WRITINGS_PATH, {"users": {}})
    )
    normalized_payload["users"][user] = {"writings": writings}
    _save_json_file(SAVED_WRITINGS_PATH, normalized_payload)


def _build_saved_writing_record(submitted_text, source_type="text", source_metadata=None, pipeline_result=None):
    sentence_mapping = (
        pipeline_result.get("sentence_mapping")
        if isinstance(pipeline_result, dict) and pipeline_result.get("sentence_mapping")
        else _load_json_file(SENTENCE_MAPPING_PATH, {"sentences": []})
    )
    output_data = (
        pipeline_result.get("output_data")
        if isinstance(pipeline_result, dict) and pipeline_result.get("output_data")
        else _load_json_file(OUTPUT_JSON_PATH, {"sentences": []})
    )
    corrected_text = (
        pipeline_result.get("corrected_text")
        if isinstance(pipeline_result, dict)
        else ""
    ) or _derive_text_from_sentence_mapping(sentence_mapping, "corrected_sentence")
    timestamp = datetime.now(timezone.utc)
    writing_id = timestamp.strftime("%Y%m%d%H%M%S%f")
    return {
        "id": writing_id,
        "title": _build_writing_title(submitted_text),
        "submitted_text": submitted_text,
        "corrected_text": corrected_text,
        "source_type": source_type,
        "source_metadata": source_metadata or {},
        "created_at": timestamp.isoformat(),
        "sentence_mapping": sentence_mapping,
        "output_data": output_data,
    }


def _saved_writing_summary(record):
    return {
        "id": record.get("id"),
        "title": record.get("title") or "Untitled writing",
        "created_at": record.get("created_at"),
    }


def _upsert_saved_writing(writings, saved_record):
    normalized_text = _normalize_writing_text(saved_record.get("submitted_text", ""))
    deduped = [
        item for item in writings
        if _normalize_writing_text(item.get("submitted_text", "")) != normalized_text
    ]
    deduped.insert(0, saved_record)
    return deduped


def _run_pipeline(source_text=None, image_path=None):
    """
    Run the shared correction/rendering pipeline with one explicit input source:
    direct user text or OCR generated from an uploaded image.
    """
    import main as pipeline_main  # type: ignore
    pipeline_main = importlib.reload(pipeline_main)

    original_use_test_data = pipeline_main.use_test_data
    original_cwd = os.getcwd()

    try:
        # Ensure sentence_mapping.json is written into renderer/run/.
        os.chdir(RUN_DIR)
        pipeline_main.use_test_data = False
        return pipeline_main.main(source_text=source_text, image_path_override=image_path)
    finally:
        pipeline_main.use_test_data = original_use_test_data
        os.chdir(original_cwd)


def _save_pipeline_result(user, source_text, source_type, source_metadata, pipeline_result):
    saved_writings = _load_saved_writings(user)
    saved_record = _build_saved_writing_record(
        source_text,
        source_type=source_type,
        source_metadata=source_metadata,
        pipeline_result=pipeline_result,
    )
    saved_writings = _upsert_saved_writing(saved_writings, saved_record)
    _save_saved_writings(user, saved_writings)
    return saved_record


def _allowed_image_filename(filename):
    _, ext = os.path.splitext(filename or "")
    return ext.lower() in ALLOWED_IMAGE_EXTENSIONS


def _find_saved_writing_record(user, writing_id):
    if not user or not writing_id:
        return None
    writings = _load_saved_writings(user)
    record = next((item for item in writings if item.get("id") == writing_id), None)
    return _repair_saved_writing_record(record) if record else None


def _tokens_to_text(tokens):
    return "".join((token or {}).get("char", "") for token in tokens or [])


def _normalize_sentence_text(text):
    return " ".join((text or "").split())


def _is_sentence_final_replacement(block, final_tokens):
    final_end = block.get("final_end")
    if not isinstance(final_end, int):
        return False
    idx = len(final_tokens) - 1
    while idx >= 0 and (final_tokens[idx].get("char", "") or "").isspace():
        idx -= 1
    return final_end >= idx


def _find_full_sentence_final_replacement_text(block, corrected_sentence):
    current = block.get("corrected_text", "")
    current_key = _normalize_sentence_text(current)
    corrected = corrected_sentence or ""
    if not current_key:
        return None

    normalized_corrected = _normalize_sentence_text(corrected)
    match_idx = normalized_corrected.find(current_key)
    if match_idx < 0:
        return None

    full_text = normalized_corrected[match_idx:]
    if len(full_text) <= len(current_key):
        return None
    return full_text


def _extend_annotation_for_replacement(sentence, block, full_text):
    annotated_tokens = sentence.get("annotated_tokens")
    if not isinstance(annotated_tokens, list):
        return False

    start = block.get("annotated_start")
    if not isinstance(start, int):
        return False

    block_id = block.get("block_index")
    required_len = start + len(full_text)
    while len(annotated_tokens) < required_len:
        annotated_tokens.append({
            "index": len(annotated_tokens),
            "char": " ",
            "type": "equal",
        })

    for offset, char in enumerate(full_text):
        idx = start + offset
        annotated_tokens[idx] = {
            **annotated_tokens[idx],
            "index": idx,
            "char": char,
            "type": "corrected",
            "replacementBlockId": block_id,
        }

    block["annotated_end"] = required_len - 1
    block["corrected_text"] = full_text
    sentence["container_length"] = max(
        int(sentence.get("container_length") or 0),
        len(sentence.get("final_sentence_tokens") or []),
        len(annotated_tokens),
    )
    return True


def _repair_saved_writing_record(record):
    """
    Repair older saved-writing snapshots that were created before annotated
    overhang was preserved during display splitting.
    """
    if not isinstance(record, dict):
        return record

    repaired = copy.deepcopy(record)
    mapping_entries = {
        item.get("sentence_index"): item
        for item in repaired.get("sentence_mapping", {}).get("sentences", [])
        if isinstance(item, dict)
    }
    sentences = repaired.get("output_data", {}).get("sentences", [])
    if not isinstance(sentences, list):
        return repaired

    for sentence in sentences:
        if sentence.get("render_mode", "token_diff") != "token_diff":
            continue

        sentence_index = sentence.get("sentence_index")
        mapping_entry = mapping_entries.get(sentence_index, {})
        corrected_sentence = mapping_entry.get("corrected_sentence", "")
        if not corrected_sentence:
            continue

        final_tokens = sentence.get("final_sentence_tokens") or []
        replacement_blocks = sentence.get("replacement_blocks") or []
        if not isinstance(final_tokens, list) or not isinstance(replacement_blocks, list):
            continue

        for block in replacement_blocks:
            if not _is_sentence_final_replacement(block, final_tokens):
                continue
            full_text = _find_full_sentence_final_replacement_text(block, corrected_sentence)
            if not full_text:
                continue
            _extend_annotation_for_replacement(sentence, block, full_text)

    return repaired

@app.route("/")
def index():
    """
    Serves the main frontend page.
    """
    return render_template("index.html")


@app.route("/auth/status", methods=["GET"])
def auth_status():
    user = _session_user()
    return jsonify({
        "authenticated": bool(user),
        "user": user,
        "available_users": list(AUTH_USERS.keys()),
    })


@app.route("/auth/login", methods=["POST"])
def auth_login():
    payload = request.get_json(silent=True) or {}
    user = (payload.get("user") or "").strip()
    password = str(payload.get("password") or "")
    expected_password = AUTH_USERS.get(user)
    if not expected_password or password != expected_password:
        session.pop("authenticated_user", None)
        return jsonify({"error": "Invalid user or password"}), 401

    session["authenticated_user"] = user
    return jsonify({"ok": True, "user": user})


@app.route("/auth/logout", methods=["POST"])
def auth_logout():
    session.pop("authenticated_user", None)
    return jsonify({"ok": True})


@app.route("/auth/mobile_upload_qr", methods=["GET"])
def auth_mobile_upload_qr():
    unauthorized = _require_authenticated_user()
    if unauthorized:
        return unauthorized
    user = _session_user()
    token = _build_mobile_upload_token(user)
    mobile_url = f"{_mobile_upload_base_url()}{url_for('mobile_upload_page', token=token)}"
    qr_image = qrcode.make(mobile_url)
    buffer = io.BytesIO()
    qr_image.save(buffer, format="PNG")
    buffer.seek(0)
    return send_file(buffer, mimetype="image/png")


@app.route("/auth/mobile_upload_heartbeat", methods=["POST"])
def auth_mobile_upload_heartbeat():
    payload = request.get_json(silent=True) or {}
    token = str(
        payload.get("token")
        or request.form.get("token")
        or request.args.get("token")
        or ""
    ).strip()
    user = _load_mobile_upload_token(token)
    if not user:
        return jsonify({"error": "Invalid mobile upload link."}), 400

    mobile_uploads = _load_mobile_uploads_payload_clean()
    record = mobile_uploads["users"].get(user)
    if not isinstance(record, dict):
        record = {}
    record["last_seen_at"] = datetime.now(timezone.utc).isoformat()
    mobile_uploads["users"][user] = record
    _save_json_file(MOBILE_UPLOADS_PATH, mobile_uploads)
    return jsonify({
        "ok": True,
        "mobile_session_active": True,
        "last_seen_at": record["last_seen_at"],
    })


@app.route("/auth/pending_mobile_upload", methods=["GET"])
def auth_pending_mobile_upload():
    unauthorized = _require_authenticated_user()
    if unauthorized:
        return unauthorized
    user = _session_user()
    record = _get_pending_mobile_upload(user)
    mobile_session_active = _mobile_upload_record_is_active(record)
    if not record:
        return jsonify({"pending": False, "mobile_session_active": mobile_session_active})
    stored_filename = record.get("stored_filename")
    if not stored_filename:
        return jsonify({
            "pending": False,
            "mobile_session_active": mobile_session_active,
        })
    return jsonify({
        "pending": True,
        "mobile_session_active": mobile_session_active,
        "image_url": url_for("uploaded_file", filename=stored_filename),
        "original_filename": record.get("original_filename", ""),
        "created_at": record.get("created_at"),
    })


@app.route("/auth/pending_mobile_upload", methods=["DELETE"])
def auth_clear_pending_mobile_upload():
    unauthorized = _require_authenticated_user()
    if unauthorized:
        return unauthorized
    user = _session_user()
    record = _clear_pending_mobile_upload(user)
    if record:
        stored_filename = record.get("stored_filename")
        _delete_uploaded_file_if_present(stored_filename)
    return jsonify({"ok": True})


@app.route("/auth/pending_mobile_upload/process", methods=["POST"])
def auth_process_pending_mobile_upload():
    unauthorized = _require_authenticated_user()
    if unauthorized:
        return unauthorized
    user = _session_user()
    record = _get_pending_mobile_upload(user)
    if not record:
        return jsonify({"error": "No pending mobile upload"}), 404

    stored_filename = record.get("stored_filename")
    if not stored_filename:
        return jsonify({"error": "Pending mobile upload is invalid"}), 400

    image_path = os.path.join(UPLOAD_DIR, stored_filename)
    if not os.path.exists(image_path):
        _clear_pending_mobile_upload(user)
        return jsonify({"error": "Pending mobile upload file is missing"}), 404

    try:
        pipeline_result = _run_pipeline(image_path=image_path)
        source_text = ((pipeline_result or {}).get("source_text") or "").strip()
        if not source_text:
            return jsonify({"error": "OCR returned no text."}), 400

        saved_record = _save_pipeline_result(
            user,
            source_text,
            source_type="image",
            source_metadata={
                "original_filename": record.get("original_filename", ""),
                "stored_filename": stored_filename,
                "source_channel": "mobile_upload",
            },
            pipeline_result=pipeline_result,
        )
        _clear_pending_mobile_upload(user)
        _delete_uploaded_file_if_present(stored_filename)
        return jsonify({
            "ok": True,
            "source_text": source_text,
            "saved_writing": _saved_writing_summary(saved_record),
            "writing": saved_record,
        })
    except ValueError as e:
        print("[ERROR] Failed to process pending mobile image:", str(e))
        return jsonify({"error": str(e)}), 400
    except Exception as e:
        print("[ERROR] Failed to process pending mobile image:", str(e))
        return jsonify({"error": "Failed to process image.", "details": str(e)}), 500


@app.route("/uploads/<path:filename>", methods=["GET"])
def uploaded_file(filename):
    unauthorized = _require_authenticated_user()
    if unauthorized:
        return unauthorized
    return send_from_directory(UPLOAD_DIR, filename)


@app.route("/mobile-upload/<token>", methods=["GET"])
def mobile_upload_page(token):
    user = _load_mobile_upload_token(token)
    if not user:
        return "Invalid mobile upload link.", 400
    return render_template("mobile_upload.html", token=token, user=user, upload_complete=False)


@app.route("/mobile-upload/<token>", methods=["POST"])
def mobile_upload_submit(token):
    user = _load_mobile_upload_token(token)
    if not user:
        return "Invalid mobile upload link.", 400

    uploaded_file = request.files.get("image") or request.files.get("file")
    if not uploaded_file or not uploaded_file.filename:
        return render_template(
            "mobile_upload.html",
            token=token,
            user=user,
            upload_complete=False,
            error="Photo is required.",
        ), 400

    original_filename = secure_filename(uploaded_file.filename)
    if not _allowed_image_filename(original_filename):
        return render_template(
            "mobile_upload.html",
            token=token,
            user=user,
            upload_complete=False,
            error="Image must be a .jpg, .jpeg, .png, or .webp file.",
        ), 400

    _, ext = os.path.splitext(original_filename)
    stored_filename = f"{datetime.now(timezone.utc).strftime('%Y%m%d%H%M%S%f')}-{uuid.uuid4().hex}{ext.lower()}"
    os.makedirs(UPLOAD_DIR, exist_ok=True)
    image_path = os.path.join(UPLOAD_DIR, stored_filename)
    uploaded_file.save(image_path)
    now_iso = datetime.now(timezone.utc).isoformat()
    _set_pending_mobile_upload(user, {
        "original_filename": original_filename,
        "stored_filename": stored_filename,
        "created_at": now_iso,
        "last_seen_at": now_iso,
    })
    return render_template("mobile_upload.html", token=token, user=user, upload_complete=True)

@app.route("/data.json")
def get_data():
    """
    Fetches and serves sentence/correction data from 'output.json' (adjust path as needed).
    """
    unauthorized = _require_authenticated_user()
    if unauthorized:
        return unauthorized
    try:
        with open(OUTPUT_JSON_PATH, "r") as f:
            data = json.load(f)
        return jsonify(data)
    except Exception as e:
        return jsonify({"error": "Failed to load output.json", "details": str(e)}), 500

@app.route("/sentence_mapping.json")
def get_sentence_mapping():
    """
    Fetches and serves OCR/corrected sentence mapping from '../sentence_mapping.json'.
    """
    unauthorized = _require_authenticated_user()
    if unauthorized:
        return unauthorized
    try:
        with open(SENTENCE_MAPPING_PATH, "r") as f:
            data = json.load(f)
        return jsonify(data)
    except Exception as e:
        return jsonify({"error": "Failed to load sentence_mapping.json", "details": str(e)}), 500


@app.route("/saved_writings", methods=["GET"])
def get_saved_writings():
    unauthorized = _require_authenticated_user()
    if unauthorized:
        return unauthorized
    try:
        user = _session_user()
        writings = _load_saved_writings(user)
        summaries = [_saved_writing_summary(record) for record in writings]
        return jsonify({"writings": summaries})
    except Exception as e:
        return jsonify({"error": "Failed to load saved writings", "details": str(e)}), 500


@app.route("/saved_writings/<writing_id>", methods=["GET"])
def get_saved_writing(writing_id):
    unauthorized = _require_authenticated_user()
    if unauthorized:
        return unauthorized
    try:
        user = _session_user()
        writings = _load_saved_writings(user)
        record = next((item for item in writings if item.get("id") == writing_id), None)
        if not record:
            return jsonify({"error": "Saved writing not found", "id": writing_id}), 404
        return jsonify(_repair_saved_writing_record(record))
    except Exception as e:
        return jsonify({"error": "Failed to load saved writing", "details": str(e)}), 500

@app.route("/highlight_click", methods=["POST"])
def highlight_click():
    """
    Handles highlight-box clicks from the frontend. 
    Calls `get_correction_explanation` to retrieve the relevant sentence/block data,
    then runs a multi-step LLM explanation via `generate_correction_explanation_single`.
    """
    unauthorized = _require_authenticated_user()
    if unauthorized:
        return unauthorized
    try:
        # 1) Parse the incoming JSON payload (blockType, blockIndex, sentenceIndex)
        data = request.get_json()
        print("[DEBUG] Received highlight click:", data)
        user = _session_user()
        writing_id = (data or {}).get("writingId")
        saved_record = _find_saved_writing_record(user, writing_id)

        # 2) Retrieve correction details (sentence/block) from JSON metadata
        correction_info = get_correction_explanation(
            data,
            sentence_mapping_override=saved_record.get("sentence_mapping") if saved_record else None,
            output_data_override=saved_record.get("output_data") if saved_record else None,
        )
        print("[DEBUG] Correction result:", correction_info)

        # 3) If there's an error (e.g. block not found), send it back
        if "error" in correction_info:
            return jsonify(correction_info), 400

        # 4) Extract fields for the explanation function
        # 4) Extract fields for the explanation function
        block_type = data.get("blockType")
        ocr_sentence = correction_info.get("ocr_sentence")
        corrected_sentence = correction_info.get("corrected_sentence")
        correction_block = correction_info.get("correction_block")
        correction_entry = correction_info.get("correction_entry")  # THIS IS MISSING!

        # 5) Generate explanation using the multi-step approach
        explanation_payload = generate_correction_explanation_single(
            block_type, ocr_sentence, corrected_sentence, correction_block, correction_entry
        )
        if isinstance(explanation_payload, dict):
            explanation = explanation_payload.get("english_explanation", "")
            korean_explanation = explanation_payload.get("korean_explanation", "")
        else:
            explanation = explanation_payload
            korean_explanation = ""

        before_text = ""
        after_text = ""
        if block_type == "replacement":
            before_text = correction_block.get("replaced_text", "")
            after_text = correction_block.get("corrected_text", "")
        elif block_type == "insert":
            before_text = ""
            after_text = correction_block.get("insert_text", "")
        elif block_type == "delete":
            before_text = correction_block.get("delete_text", "")
            after_text = ""

        result = {
            "explanation": explanation,
            "korean_explanation": korean_explanation,
            "before_text": before_text,
            "after_text": after_text,
            "display_sentence": copy.deepcopy(correction_entry),
        }

        # 6) Return the explanation as JSON
        return jsonify(result)
    except Exception as e:
        print("[ERROR] Failed to process highlight click:", str(e))
        return jsonify({"error": "Internal server error", "details": str(e)}), 500

@app.route("/analyze_text", methods=["POST"])
def analyze_text():
    """
    Runs the shared pipeline using direct user-submitted text as the source.
    """
    unauthorized = _require_authenticated_user()
    if unauthorized:
        return unauthorized
    payload = request.get_json(silent=True) or {}
    submitted_text = (payload.get("submitted_text") or "").strip()
    if not submitted_text:
        return jsonify({"error": "submitted_text is required"}), 400

    try:
        user = _session_user()
        pipeline_result = _run_pipeline(source_text=submitted_text)
        saved_record = _save_pipeline_result(
            user,
            submitted_text,
            source_type="text",
            source_metadata={},
            pipeline_result=pipeline_result,
        )

        return jsonify({
            "ok": True,
            "saved_writing": _saved_writing_summary(saved_record),
            "writing": saved_record,
        })
    except Exception as e:
        print("[ERROR] Failed to run analyze_text pipeline:", str(e))
        return jsonify({"error": "Failed to run pipeline", "details": str(e)}), 500


@app.route("/analyze_image", methods=["POST"])
def analyze_image():
    """
    Runs the shared pipeline using OCR extracted from an uploaded image.
    """
    unauthorized = _require_authenticated_user()
    if unauthorized:
        return unauthorized
    uploaded_file = request.files.get("image") or request.files.get("file")
    if not uploaded_file or not uploaded_file.filename:
        return jsonify({"error": "image file is required"}), 400

    original_filename = secure_filename(uploaded_file.filename)
    if not _allowed_image_filename(original_filename):
        return jsonify({"error": "image must be a .jpg, .jpeg, .png, or .webp file"}), 400

    _, ext = os.path.splitext(original_filename)
    stored_filename = f"{datetime.now(timezone.utc).strftime('%Y%m%d%H%M%S%f')}-{uuid.uuid4().hex}{ext.lower()}"
    os.makedirs(UPLOAD_DIR, exist_ok=True)
    image_path = os.path.join(UPLOAD_DIR, stored_filename)
    uploaded_file.save(image_path)

    try:
        user = _session_user()
        pipeline_result = _run_pipeline(image_path=image_path)
        source_text = ((pipeline_result or {}).get("source_text") or "").strip()
        if not source_text:
            return jsonify({"error": "OCR returned no text"}), 400

        saved_record = _save_pipeline_result(
            user,
            source_text,
            source_type="image",
            source_metadata={
                "original_filename": original_filename,
                "stored_filename": stored_filename,
            },
            pipeline_result=pipeline_result,
        )

        return jsonify({
            "ok": True,
            "source_text": source_text,
            "saved_writing": _saved_writing_summary(saved_record),
            "writing": saved_record,
        })
    except Exception as e:
        print("[ERROR] Failed to run analyze_image pipeline:", str(e))
        return jsonify({"error": "Failed to run image pipeline", "details": str(e)}), 500

if __name__ == "__main__":
    """
    Runs the Flask app (development mode).
    In production, use a WSGI server (e.g. Gunicorn) instead:
      gunicorn -b 0.0.0.0:5000 app:app
    """
    app.run(debug=True, host="0.0.0.0", port=5000)
