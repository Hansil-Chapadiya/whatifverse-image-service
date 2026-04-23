from fastapi import FastAPI

from app.api.v1.router import router as v1_router
from app.core.config import settings
from app.core.errors import register_error_handlers
from app.db.session import check_db_connection, init_db

app = FastAPI(title=settings.app_name, debug=settings.debug)
app.include_router(v1_router, prefix=settings.api_v1_prefix)
register_error_handlers(app)


@app.on_event("startup")
def startup_db() -> None:
	# If DATABASE_URL is configured, verify Neon DB connectivity and ensure tables exist.
	if settings.database_url:
		check_db_connection()
		init_db()
