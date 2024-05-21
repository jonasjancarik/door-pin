from fastapi import FastAPI, HTTPException
import json
import utils

app = FastAPI()


# Load the tokens from a JSON file
def load_tokens():
    try:
        with open("tokens.json", "r") as file:
            return json.load(file)
    except FileNotFoundError:
        return {}


@app.get("/door/unlock")
@app.get("/door/unlock/")
def api_unlock_door(username: str, token: str):
    tokens = load_tokens()
    hashed_token = utils.hash_secret(salt=username, payload=token)
    if tokens.get(username)["hashed_token"] == hashed_token:
        try:
            utils.unlock_door()
            return {"message": "Door unlocked successfully"}
        except Exception as e:
            # Coudln't unlock the door for some reason
            raise HTTPException(status_code=500, detail=str(e))
    else:
        raise HTTPException(status_code=401, detail="Unauthorized")


if __name__ == "__main__":
    import uvicorn

    uvicorn.run(app, host="0.0.0.0", port=8000)
