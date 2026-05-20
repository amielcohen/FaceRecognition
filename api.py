from pathlib import Path
import shutil
import sqlite3
from uuid import uuid4
import json
from fastapi import (
    FastAPI,
    Query,
    HTTPException,
    UploadFile,
    File,
)
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import FileResponse
from fastapi.staticfiles import StaticFiles
import subprocess
import sys
import time
from fastapi.responses import StreamingResponse

BASE_DIR = Path(__file__).resolve().parent

DB_PATH = BASE_DIR / "database" / "vision_db.sqlite"

EMBEDDINGS_PATH = BASE_DIR / "storage" / "employees_embeddings.json"
EMPLOYEES_ROOT = BASE_DIR / "employees_data"

MAIN_SCRIPT_PATH = BASE_DIR / "main.py"
recognition_process = None
recognition_status = "stopped"

app = FastAPI()


app.mount(
    "/employees_data",
    StaticFiles(directory=EMPLOYEES_ROOT),
    name="employees_data",
)


app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

def is_recognition_running():
    global recognition_process

    if recognition_process is None:
        return False

    return recognition_process.poll() is None

def get_db_connection():
    if not DB_PATH.exists():
        raise HTTPException(
            status_code=404,
            detail="Database file not found",
        )

    conn = sqlite3.connect(DB_PATH)

    conn.row_factory = sqlite3.Row

    return conn

CAMERA_PRESETS = {
    "fast": {
        "preset": "fast",
        "min_face_area": 3500,
        "area_update_ratio": 1.0,
        "match_identity_threshold": 0.40,
        "lock_identity_threshold": 0.30,
        "max_unknown_attempts": 3,
        "frame_skip_interval": 3,
        "retention_hours": 12,
        "segment_minutes": 120,
        "record_res_width": 960,
        "record_fps": 10,
    },

    "balanced": {
        "preset": "balanced",
        "min_face_area": 2500,
        "area_update_ratio": 1.2,
        "match_identity_threshold": 0.40,
        "lock_identity_threshold": 0.20,
        "max_unknown_attempts": 5,
        "frame_skip_interval": 1,
        "retention_hours": 24,
        "segment_minutes": 60,
        "record_res_width": 1280,
        "record_fps": 15,
    },

    "accurate": {
        "preset": "accurate",
        "min_face_area": 1800,
        "area_update_ratio": 1.5,
        "match_identity_threshold": 0.38,
        "lock_identity_threshold": 0.15,
        "max_unknown_attempts": 8,
        "frame_skip_interval": 1,
        "retention_hours": 48,
        "segment_minutes": 30,
        "record_res_width": 1920,
        "record_fps": 25,
    },
}


def remove_employee_from_embeddings(folder_name: str):
    if not EMBEDDINGS_PATH.exists():
        return

    with open(EMBEDDINGS_PATH, "r", encoding="utf-8") as file:
        embeddings_data = json.load(file)

    if folder_name in embeddings_data:
        del embeddings_data[folder_name]

    with open(EMBEDDINGS_PATH, "w", encoding="utf-8") as file:
        json.dump(embeddings_data, file, indent=2)


# =========================================================
# General Routes
# =========================================================

@app.get("/status")
def get_status():
    return {
        "status": "running"
    }


# =========================================================
# Attendance Routes
# =========================================================

@app.get("/attendance-logs")
def get_attendance_logs(
    limit: int = Query(default=100, ge=1, le=500),
    offset: int = Query(default=0, ge=0),
):
    with get_db_connection() as conn:
        cursor = conn.cursor()

        cursor.execute(
            """
            SELECT
                id,
                identity_id,
                matched_name,
                distance,
                track_id,
                entry_time,
                crop_path
            FROM attendance_logs
            ORDER BY entry_time DESC
            LIMIT ? OFFSET ?
            """,
            (limit, offset),
        )

        items = [dict(row) for row in cursor.fetchall()]

        cursor.execute(
            "SELECT COUNT(*) AS total FROM attendance_logs"
        )

        total = cursor.fetchone()["total"]

    return {
        "total": total,
        "limit": limit,
        "offset": offset,
        "items": items,
    }


@app.get("/attendance-crop")
def get_attendance_crop(path: str):
    # Normalize backslashes to forward slashes
    path = path.replace("\\", "/")
    
    crop_path = Path(path)

    if not crop_path.is_absolute():
        crop_path = BASE_DIR / crop_path

    if not crop_path.exists():
        raise HTTPException(
            status_code=404,
            detail="Crop image not found",
        )

    return FileResponse(crop_path)


# =========================================================
# Employees Routes
# =========================================================

@app.get("/employees")
def get_employees():
    EMPLOYEES_ROOT.mkdir(exist_ok=True)

    employees = []

    for employee_dir in EMPLOYEES_ROOT.iterdir():

        if not employee_dir.is_dir():
            continue

        image_files = [
            file
            for file in employee_dir.iterdir()
            if file.suffix.lower() in [
                ".jpg",
                ".jpeg",
                ".png",
            ]
        ]

        preview_image = None

        if image_files:
            relative_path = image_files[0].relative_to(BASE_DIR)

            preview_image = str(relative_path).replace(
                "\\",
                "/",
            )

        employees.append({
            "display_name": employee_dir.name.replace(
                "_",
                " ",
            ).title(),

            "folder_name": employee_dir.name,

            "images_count": len(image_files),

            "preview_image": preview_image,
        })

    employees.sort(
        key=lambda employee: employee["display_name"]
    )

    return {
        "items": employees
    }


@app.post("/employees")
def create_employee(data: dict):
    first_name = data.get("first_name", "").strip()
    last_name = data.get("last_name", "").strip()

    if not first_name or not last_name:
        raise HTTPException(
            status_code=400,
            detail="First name and last name are required",
        )

    folder_name = f"{first_name}_{last_name}".lower().replace(" ", "_")
    employee_path = EMPLOYEES_ROOT / folder_name

    if employee_path.exists():
        raise HTTPException(
            status_code=400,
            detail="Employee already exists",
        )

    employee_path.mkdir(parents=True, exist_ok=False)

    try:
        with get_db_connection() as conn:
            conn.execute(
                """
                INSERT INTO identities (name)
                VALUES (?)
                """,
                (folder_name,),
            )
            conn.commit()
    except sqlite3.IntegrityError:
        shutil.rmtree(employee_path)
        raise HTTPException(
            status_code=400,
            detail="Employee already exists in database",
        )

    return {
        "message": "Employee created successfully",
        "folder_name": folder_name,
    }

@app.delete("/employees/{folder_name}")
def delete_employee(folder_name: str):
    employee_path = EMPLOYEES_ROOT / folder_name

    if not employee_path.exists():
        raise HTTPException(
            status_code=404,
            detail="Employee not found",
        )

    shutil.rmtree(employee_path)

    with get_db_connection() as conn:
        conn.execute(
            """
            DELETE FROM identities
            WHERE name = ?
            """,
            (folder_name,),
        )
        conn.commit()

    remove_employee_from_embeddings(folder_name)

    return {
        "message": "Employee deleted successfully"
    }


@app.post("/employees/{folder_name}/images")
async def upload_employee_images(
    folder_name: str,
    files: list[UploadFile] = File(...),
):
    employee_path = EMPLOYEES_ROOT / folder_name

    if not employee_path.exists():
        raise HTTPException(
            status_code=404,
            detail="Employee not found",
        )

    allowed_extensions = [
        ".jpg",
        ".jpeg",
        ".png",
    ]

    saved_files = []

    for file in files:

        extension = (
            Path(file.filename)
            .suffix
            .lower()
        )

        if extension not in allowed_extensions:
            continue

        unique_name = (
            f"{uuid4().hex}{extension}"
        )

        destination = (
            employee_path / unique_name
        )

        with open(destination, "wb") as buffer:
            shutil.copyfileobj(
                file.file,
                buffer,
            )

        saved_files.append(unique_name)

    return {
        "message": "Images uploaded successfully",
        "saved_files": saved_files,
    }

@app.post("/rebuild-embeddings")
def rebuild_embeddings():
    script_path = BASE_DIR / "build_embeddings.py"

    if not script_path.exists():
        raise HTTPException(
            status_code=404,
            detail="build_embeddings.py not found",
        )

    try:
        result = subprocess.run(
            [sys.executable, str(script_path)],
            capture_output=True,
            text=True,
            check=True,
        )

        return {
            "message": "Embeddings rebuilt successfully",
            "output": result.stdout,
        }

    except subprocess.CalledProcessError as e:
        raise HTTPException(
            status_code=500,
            detail=e.stderr,
        )
    
    
# =========================================================
# Dashboard Routes
# =========================================================


@app.get("/dashboard")
def get_dashboard():
    global recognition_status
    employees_count = 0

    if not is_recognition_running() and recognition_status != "stopped":
        recognition_status = "stopped"

    if EMPLOYEES_ROOT.exists():
        employees_count = len([
            item for item in EMPLOYEES_ROOT.iterdir()
            if item.is_dir()
        ])

    with get_db_connection() as conn:
        logs_today = conn.execute(
            """
            SELECT COUNT(*) AS total
            FROM attendance_logs
            WHERE date(entry_time) = date('now')
            """
        ).fetchone()["total"]

        unknown_today = conn.execute(
            """
            SELECT COUNT(*) AS total
            FROM attendance_logs
            WHERE date(entry_time) = date('now')
            AND lower(matched_name) = 'unknown'
            """
        ).fetchone()["total"]

        last_recognition = conn.execute(
            """
            SELECT entry_time
            FROM attendance_logs
            ORDER BY entry_time DESC
            LIMIT 1
            """
        ).fetchone()

    return {
      "status": recognition_status,
        "stats": {
            "employees_count": employees_count,
            "logs_today": logs_today,
            "unknown_today": unknown_today,
            "last_recognition": last_recognition["entry_time"] if last_recognition else None,
        }
    }

@app.post("/system/start")
def start_system():
    global recognition_process
    global recognition_status

    if is_recognition_running():
        return {
            "message": "Recognition system is already running",
            "status": recognition_status,
        }

    if not MAIN_SCRIPT_PATH.exists():
        raise HTTPException(
            status_code=404,
            detail="main.py not found",
        )

    recognition_status = "starting"

    recognition_process = subprocess.Popen(
        [sys.executable, str(MAIN_SCRIPT_PATH)],
        cwd=str(BASE_DIR),
    )

    return {
        "message": "Recognition system is starting",
        "status": "starting",
    }

@app.post("/system/mark-ready")
def mark_system_ready():
    global recognition_status

    recognition_status = "running"

    return {
        "message": "System marked as ready"
    }


@app.post("/system/stop")
def stop_system():
    global recognition_process
    global recognition_status

    recognition_status = "stopped"

    if not is_recognition_running():
        return {
            "message": "Recognition system is already stopped",
            "status": "stopped",
        }

    recognition_process.terminate()

    try:
        recognition_process.wait(timeout=10)
    except subprocess.TimeoutExpired:
        recognition_process.kill()
        recognition_process.wait()

    recognition_process = None

    return {
        "message": "Recognition system stopped",
        "status": "stopped",
    }


@app.post("/system/restart")
def restart_system():
    stop_system()
    return start_system()


# =========================================================
# Camera Settings Routes
# =========================================================

@app.get("/camera-settings")
def get_camera_settings():
    with get_db_connection() as conn:
        cursor = conn.cursor()

        cursor.execute("""
            SELECT *
            FROM camera_settings
            WHERE id = 1
        """)

        row = cursor.fetchone()

        if not row:
            raise HTTPException(
                status_code=404,
                detail="Camera settings not found",
            )

        settings = dict(row)

        if "preset" not in settings:
            settings["preset"] = "balanced"

        return settings


@app.put("/camera-settings")
def update_camera_settings(settings: dict):
    allowed_fields = {
        "min_face_area",
        "area_update_ratio",
        "match_identity_threshold",
        "lock_identity_threshold",
        "max_unknown_attempts",
        "frame_skip_interval",
        "retention_hours",
        "segment_minutes",
        "record_res_width",
        "record_fps",
        "preset",
    }

    update_fields = {
        key: value
        for key, value in settings.items()
        if key in allowed_fields
    }

    if not update_fields:
        raise HTTPException(
            status_code=400,
            detail="No valid fields provided",
        )

    set_clause = ", ".join([
        f"{key} = ?"
        for key in update_fields.keys()
    ])

    values = list(update_fields.values())

    values.append(1)

    with get_db_connection() as conn:
        cursor = conn.cursor()

        cursor.execute(
            f"""
            UPDATE camera_settings
            SET {set_clause}
            WHERE id = ?
            """,
            values,
        )

        conn.commit()

    return {
        "message": "Camera settings updated successfully",
        "settings": get_camera_settings(),
    }


@app.post("/camera-settings/preset/{preset_name}")
def apply_camera_preset(preset_name: str):
    if preset_name not in CAMERA_PRESETS:
        raise HTTPException(
            status_code=400,
            detail="Invalid preset name",
        )

    preset_settings = CAMERA_PRESETS[preset_name]

    allowed_fields = {
        "preset",
        "min_face_area",
        "area_update_ratio",
        "match_identity_threshold",
        "lock_identity_threshold",
        "max_unknown_attempts",
        "frame_skip_interval",
        "retention_hours",
        "segment_minutes",
        "record_res_width",
        "record_fps",
    }

    update_fields = {
        key: value
        for key, value in preset_settings.items()
        if key in allowed_fields
    }

    set_clause = ", ".join([
        f"{key} = ?"
        for key in update_fields.keys()
    ])

    values = list(update_fields.values())

    values.append(1)

    with get_db_connection() as conn:
        cursor = conn.cursor()

        cursor.execute(
            f"""
            UPDATE camera_settings
            SET {set_clause}
            WHERE id = ?
            """,
            values,
        )

        conn.commit()

    return {
        "message": f"{preset_name} preset applied successfully",
        "settings": get_camera_settings(),
    }


@app.post("/camera-settings/reset")
def reset_camera_settings():
    return apply_camera_preset("balanced")

# =========================================================
# Live Monitor Routes
# =========================================================


LATEST_FRAME_PATH = BASE_DIR / "data" / "latest_frame.jpg"


def generate_frames():
    """Read latest_frame.jpg from disk and stream it as MJPEG."""
    while True:
        if not LATEST_FRAME_PATH.exists():
            time.sleep(0.1)
            continue

        try:
            with open(LATEST_FRAME_PATH, "rb") as f:
                frame_bytes = f.read()

            yield (
                b"--frame\r\n"
                b"Content-Type: image/jpeg\r\n\r\n"
                + frame_bytes
                + b"\r\n"
            )
        except Exception:
            pass

        time.sleep(0.033)  # ~30fps read rate


@app.get("/video-feed")
def video_feed():
    return StreamingResponse(
        generate_frames(),
        media_type="multipart/x-mixed-replace; boundary=frame"
    )