import os

import uvicorn

if __name__ == "__main__":
    uvicorn.run(
        "dell_repro.app:app", host="127.0.0.1", port=int(os.getenv("DELL_REPRO_PORT", "8100"))
    )
