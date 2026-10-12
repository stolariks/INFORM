from pathlib import Path
from functools import lru_cache


from contextlib import asynccontextmanager
from fastapi import FastAPI, Request, Depends
from typing import Annotated

from fiber_response.dependencies import Settings, get_settings
from fiber_response.routers import files, compute

@asynccontextmanager
async def lifespan(app: FastAPI):
    app.state.experiment = None
    yield

app = FastAPI(lifespan=lifespan)
app.include_router(compute.router)
app.include_router(files.router)


@app.get("/")
async def get_data_dir(settings: Annotated[Settings, Depends(get_settings)]):
    return {"data_dir": settings.data_dir}

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

