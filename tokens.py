import hashlib
import json
import datetime

# Load existing tokens from a JSON file
def load_tokens():
    try:
        with open('tokens.json', 'r') as file:
            return json.load(file)
    except FileNotFoundError:
        return {}

# Save tokens to a JSON file
def save_tokens(tokens):
    with open('tokens.json', 'w') as file:
        json.dump(tokens, file, indent=4)

# Hash the token using SHA-256
def hash_token(username, token):
    salted_token = f"{username}{token}"
    return hashlib.sha256(salted_token.encode('utf-8')).hexdigest()

def create_token():
    tokens = load_tokens()
    username = input("Enter the username: ")
    token = input("Enter a new token: ")
    hashed_token = hash_token(username, token)
    tokens[username] = {
        'hashed_token': hashed_token,
        'created_at': datetime.datetime.now().isoformat()
    }
    save_tokens(tokens)
    print(f"Token for {username} created and stored successfully.")

if __name__ == "__main__":
    create_token()