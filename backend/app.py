from fastapi import FastAPI

app = FastAPI(title="ArchLens API")


@app.get("/")
def root():
    return {
        "project": "ArchLens",
        "status": "running"
    }
