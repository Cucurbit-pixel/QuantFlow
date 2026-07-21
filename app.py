from fastapi import FastAPI, BackgroundTasks
from screener.merge import run_full_scan

app = FastAPI(title="QuantFlow")

@app.get("/")
def root():
    return {"message": "QuantFlow is running", "status": "ok"}

@app.post("/scan")
def trigger_scan(background_tasks: BackgroundTasks):
    background_tasks.add_task(run_full_scan)
    return {"message": "Scan triggered in background"}

if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="0.0.0.0", port=8000)