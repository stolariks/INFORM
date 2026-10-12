"""
@file: main.py
@author: Samuel Stolarik
@description:
    Platform running
    code and API declaration
"""

from pathlib import Path
from functools import lru_cache
from typing import Annotated

from contextlib import asynccontextmanager
from fastapi import FastAPI, Request, Depends
from fastapi.staticfiles import StaticFiles
from fastapi.responses import FileResponse

from fiber_response.dependencies import Settings, get_settings
from fiber_response.routers import files, compute, experiment
import fiber_response

platform_root = Path(fiber_response.__path__[0])

@asynccontextmanager
async def lifespan(app: FastAPI):
    app.state.experiment = None
    yield

app = FastAPI(
    title="Simulation platform",
    summary="Connector for INFORM",
    lifespan=lifespan
)
app.include_router(compute.router)
app.include_router(files.router)
app.include_router(experiment.router)

app.mount("/assets", StaticFiles(directory=platform_root/"public/assets"), name="static")

@app.get("/", response_class=FileResponse)
async def app_main():
    global platform_root
    return platform_root / "public/index.html"

def main():
    args = parse_args()

    # Make sure data dir exists
    args.data_dir.mkdir(parents=True, exist_ok=True)

    uvicorn.run(
        create_app(args.data_dir),
        host=args.host,
        port=args.port
    )


if __name__=="__main__":
    main()

