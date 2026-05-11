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

BASE_DIR = Path(__file__).resolve().parent

DB_PATH = BASE_DIR / "database" / "vision_db.sqlite"

EMBEDDINGS_PATH = BASE_DIR / "storage" / "employees_embeddings.json"
EMPLOYEES_ROOT = BASE_DIR / "employees_data"


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



def get_db_connection():
    if not DB_PATH.exists():
        raise HTTPException(
            status_code=404,
            detail="Database file not found",
        )

    conn = sqlite3.connect(DB_PATH)

    conn.row_factory = sqlite3.Row

    return conn

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