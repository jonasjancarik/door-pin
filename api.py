from fastapi import FastAPI, HTTPException
import hashlib
import datetime
import json
from typing import Optional

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

# Unlock the door (simulate GPIO action)
def unlock_door():
    print("Door unlocked!")
    # Here you would add the actual GPIO code to unlock the door
    # GPIO.output(RELAY_PIN, GPIO.HIGH)
    # time.sleep(RELAY_ACTIVATION_TIME)
    # GPIO.output(RELAY_PIN, GPIO.LOW)

@app.get("/unlock_door")
@app.get("/unlock_door/")
def api_unlock_door(username: str, token: str):
    tokens = load_tokens()
    hashed_token = hash_token(username, token)
    if tokens.get(username)['hashed_token'] == hashed_token:
        unlock_door()
        return {"message": "Door unlocked successfully"}
    else:
        raise HTTPException(status_code=401, detail="Unauthorized")

if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="0.0.0.0", port=8000)
