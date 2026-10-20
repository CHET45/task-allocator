"""Application entry point: data API, algorithm, Jira stub, Forge Storage and the plugin UI."""
import json
import os
from pathlib import Path

from fastapi import FastAPI
from fastapi.staticfiles import StaticFiles
from sqlalchemy import func, select

from . import api, jira_stub
from .db import Base, make_session_factory
from .forge_storage import DEFAULTS, ForgeStorage
from .jira_stub import JiraStore
from .models import Skill
from .seed import seed_database, write_jira

ROOT = Path(__file__).resolve().parent.parent
STATIC_DIR = ROOT / "static"


def settings_from_env() -> tuple[str, Path]:
    data_dir = Path(os.environ.get("DATA_DIR", ROOT / "data"))
    data_dir.mkdir(parents=True, exist_ok=True)
    url = os.environ.get("DATABASE_URL", f"sqlite:///{(data_dir / 'allocator.db').as_posix()}")
    return url, data_dir


def _write_catalog_cache(forge: ForgeStorage, SessionLocal) -> None:
    with SessionLocal() as db:
        items = [{"id": s.id, "name": s.name, "category": s.category}
                 for s in db.scalars(select(Skill).order_by(Skill.category, Skill.name))]
    forge.set("skills.catalog", {"version": forge.get("skills.catalog").get("version", 0) + 1, "items": items})


def reset_demo_data(database_url: str, data_dir: Path, app: FastAPI | None = None) -> None:
    engine, SessionLocal = make_session_factory(database_url)
    Base.metadata.drop_all(engine)
    Base.metadata.create_all(engine)
    with SessionLocal() as db:
        seed_database(db)
    write_jira(data_dir / "jira.json")
    (data_dir / "forge_storage.json").write_text(json.dumps(DEFAULTS, ensure_ascii=False, indent=2), encoding="utf-8")
    forge = ForgeStorage(data_dir / "forge_storage.json")
    _write_catalog_cache(forge, SessionLocal)
    if app is not None:
        app.state.engine, app.state.SessionLocal = engine, SessionLocal
        app.state.forge = forge
    else:
        engine.dispose()


def create_app(database_url: str | None = None, data_dir: Path | None = None) -> FastAPI:
    env_url, env_dir = settings_from_env()
    database_url = database_url or env_url
    data_dir = Path(data_dir or env_dir)
    data_dir.mkdir(parents=True, exist_ok=True)

    app = FastAPI(
        title="Dinamiska darba uzdevumu sadales sistēma",
        version="1.0.0",
        description="Prototips: sadales algoritms, datu piekļuves API, Jira REST API aizstājējs.",
    )
    app.state.database_url, app.state.data_dir = database_url, data_dir

    engine, SessionLocal = make_session_factory(database_url)
    Base.metadata.create_all(engine)
    with SessionLocal() as db:
        empty = db.scalar(select(func.count()).select_from(Skill)) == 0
    if empty or not (data_dir / "jira.json").exists():
        engine.dispose()
        reset_demo_data(database_url, data_dir, app=app)
    else:
        app.state.engine, app.state.SessionLocal = engine, SessionLocal
        app.state.forge = ForgeStorage(data_dir / "forge_storage.json")
    app.state.jira = JiraStore(data_dir / "jira.json")

    app.include_router(api.router)
    app.include_router(api.forge_router)
    app.include_router(jira_stub.router)
    app.mount("/", StaticFiles(directory=STATIC_DIR, html=True), name="ui")
    return app
