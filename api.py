from fastapi import FastAPI, HTTPException
import hashlib
import json
import utils

app = FastAPI()

# Load the tokens from a JSON file
def load_tokens():
    try:
        with open('tokens.json', 'r') as file:
            return json.load(file)
    except FileNotFoundError:
        return {}

# Hash the token using SHA-256
def hash_token(username, token):
    salted_token = f"{username}{token}"
    return hashlib.sha256(salted_token.encode('utf-8')).hexdigest()

# Unlock the door
def unlock_door():
    utils.unlock_door()


@app.get("/door/unlock")
@app.get("/door/unlock/")
def api_unlock_door(username: str, token: str):
    tokens = load_tokens()
    hashed_token = hash_token(username, token)
    if tokens.get(username)['hashed_token'] == hashed_token:
        try:
            unlock_door()
            return {"message": "Door unlocked successfully"}
        except Exception as e:
            # Coudln't unlock the door for some reason
            raise HTTPException(status_code=500, detail=str(e))
    else:
        raise HTTPException(status_code=401, detail="Unauthorized")

if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="0.0.0.0", port=8000)
