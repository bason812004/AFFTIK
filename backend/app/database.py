import sqlite3
import json
import logging
from typing import Any, Tuple
from backend.app.config import DB_PATH
from backend.app.services.prompt_templates import DEFAULT_SYSTEM_PROMPTS

logger = logging.getLogger(__name__)

class AsyncCursor:
    def __init__(self, cursor: sqlite3.Cursor):
        self._cur = cursor

    async def fetchall(self):
        return self._cur.fetchall()

    async def fetchone(self):
        return self._cur.fetchone()

class AsyncDatabase:
    def __init__(self, conn: sqlite3.Connection):
        self._conn = conn

    async def execute(self, sql: str, params: Tuple[Any, ...] = ()):
        cur = self._conn.execute(sql, params)
        return AsyncCursor(cur)

    async def commit(self):
        self._conn.commit()

    async def close(self):
        self._conn.close()

    async def __aenter__(self):
        return self

    async def __aexit__(self, exc_type, exc_val, exc_tb):
        if exc_type:
            self._conn.rollback()
        else:
            self._conn.commit()

def _get_raw_conn() -> sqlite3.Connection:
    conn = sqlite3.connect(str(DB_PATH), timeout=10.0, check_same_thread=False)
    conn.row_factory = sqlite3.Row
    return conn

def get_setting(key: str, default: str = "") -> str:
    try:
        conn = _get_raw_conn()
        cur = conn.execute("SELECT value FROM settings WHERE key = ?", (key,))
        row = cur.fetchone()
        conn.close()
        return row["value"] if row else default
    except Exception:
        return default

def set_setting(key: str, value: str):
    try:
        conn = _get_raw_conn()
        conn.execute("""
            INSERT INTO settings (key, value, updated_at) VALUES (?, ?, CURRENT_TIMESTAMP)
            ON CONFLICT(key) DO UPDATE SET value = excluded.value, updated_at = CURRENT_TIMESTAMP
        """, (key, str(value)))
        conn.commit()
        conn.close()
    except Exception as e:
        logger.error(f"Error saving setting {key}: {e}")

async def get_db():
    conn = _get_raw_conn()
    db = AsyncDatabase(conn)
    try:
        yield db
    finally:
        await db.close()

def init_db():
    conn = _get_raw_conn()
    
    # Projects
    conn.execute("""
    CREATE TABLE IF NOT EXISTS projects (
        id TEXT PRIMARY KEY,
        name TEXT NOT NULL,
        category TEXT,
        description TEXT,
        benefits TEXT,
        highlights TEXT,
        materials TEXT,
        target_customer TEXT,
        usage_guide TEXT,
        price TEXT,
        offer TEXT,
        warranty TEXT,
        notes TEXT,
        tiktok_url TEXT,
        original_image_path TEXT,
        primary_character_image_path TEXT,
        selected_script_id TEXT,
        status TEXT DEFAULT 'created',
        automation_mode TEXT DEFAULT 'auto',
        created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
        updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
    );
    """)

    # Assets
    conn.execute("""
    CREATE TABLE IF NOT EXISTS assets (
        id TEXT PRIMARY KEY,
        project_id TEXT NOT NULL,
        asset_type TEXT NOT NULL,
        file_path TEXT NOT NULL,
        file_name TEXT NOT NULL,
        file_size INTEGER,
        width INTEGER,
        height INTEGER,
        duration_seconds REAL,
        is_primary BOOLEAN DEFAULT 0,
        created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
        FOREIGN KEY (project_id) REFERENCES projects(id) ON DELETE CASCADE
    );
    """)

    # Prompts library
    conn.execute("""
    CREATE TABLE IF NOT EXISTS prompts (
        id TEXT PRIMARY KEY,
        project_id TEXT,
        category TEXT NOT NULL,
        title TEXT NOT NULL,
        content TEXT NOT NULL,
        variables_json TEXT,
        is_default BOOLEAN DEFAULT 0,
        is_system BOOLEAN DEFAULT 0,
        created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
        updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
    );
    """)

    # Scripts (3 options A/B/C)
    conn.execute("""
    CREATE TABLE IF NOT EXISTS scripts (
        id TEXT PRIMARY KEY,
        project_id TEXT NOT NULL,
        option_label TEXT NOT NULL,
        option_title TEXT,
        hook_concept TEXT,
        scene1_dialogue TEXT,
        scene1_word_count INTEGER DEFAULT 0,
        scene1_prompt_veo TEXT,
        scene2_dialogue TEXT,
        scene2_word_count INTEGER DEFAULT 0,
        scene2_prompt_veo TEXT,
        is_selected BOOLEAN DEFAULT 0,
        raw_response TEXT,
        created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
        updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
        FOREIGN KEY (project_id) REFERENCES projects(id) ON DELETE CASCADE
    );
    """)

    # Videos (Scene 1 & Scene 2)
    conn.execute("""
    CREATE TABLE IF NOT EXISTS videos (
        id TEXT PRIMARY KEY,
        project_id TEXT NOT NULL,
        script_id TEXT,
        scene_number INTEGER NOT NULL,
        video_path TEXT NOT NULL,
        duration REAL,
        resolution TEXT,
        fps REAL,
        status TEXT DEFAULT 'ready',
        error_message TEXT,
        created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
        FOREIGN KEY (project_id) REFERENCES projects(id) ON DELETE CASCADE
    );
    """)

    # Exports
    conn.execute("""
    CREATE TABLE IF NOT EXISTS exports (
        id TEXT PRIMARY KEY,
        project_id TEXT NOT NULL,
        final_video_path TEXT NOT NULL,
        file_name TEXT NOT NULL,
        duration REAL,
        resolution TEXT,
        fps REAL,
        file_size INTEGER,
        audio_info TEXT,
        created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
        FOREIGN KEY (project_id) REFERENCES projects(id) ON DELETE CASCADE
    );
    """)

    # Automation Tasks
    conn.execute("""
    CREATE TABLE IF NOT EXISTS automation_tasks (
        id TEXT PRIMARY KEY,
        project_id TEXT,
        task_type TEXT NOT NULL,
        status TEXT NOT NULL,
        step_name TEXT,
        progress_percent INTEGER DEFAULT 0,
        message TEXT,
        log_details TEXT,
        error_message TEXT,
        created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
        updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
    );
    """)

    # App Settings
    conn.execute("""
    CREATE TABLE IF NOT EXISTS settings (
        key TEXT PRIMARY KEY,
        value TEXT NOT NULL,
        updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
    );
    """)

    conn.commit()

    # Seed defaults
    defaults = {
        "gemini_url": "https://gemini.google.com/app",
        "flow_url": "https://labs.google/flow",
        "target_duration": "10",
        "target_word_count": "42",
        "aspect_ratio": "9:16",
        "target_resolution": "1080x1920",
        "target_fps": "30",
        "output_format": "mp4",
        "voice_gender": "female",
        "voice_accent": "northern_hanoi",
        "voice_tone": "friendly_consultative",
        "default_mode": "auto"
    }
    for k, v in defaults.items():
        conn.execute(
            "INSERT OR IGNORE INTO settings (key, value, updated_at) VALUES (?, ?, CURRENT_TIMESTAMP)",
            (k, v)
        )

    for prompt in DEFAULT_SYSTEM_PROMPTS:
        conn.execute("""
            INSERT INTO prompts (
                id, project_id, category, title, content, variables_json, is_default, is_system, created_at, updated_at
            ) VALUES (?, NULL, ?, ?, ?, ?, 1, 1, CURRENT_TIMESTAMP, CURRENT_TIMESTAMP)
            ON CONFLICT(id) DO UPDATE SET
                title = excluded.title,
                content = excluded.content,
                variables_json = excluded.variables_json,
                updated_at = CURRENT_TIMESTAMP
        """, (
            prompt["id"],
            prompt["category"],
            prompt["title"],
            prompt["content"],
            json.dumps(prompt.get("variables", []))
        ))

    conn.commit()
    conn.close()

def seed_default_prompts():
    init_db()
