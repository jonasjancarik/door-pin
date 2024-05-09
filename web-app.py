from dash import Dash, html, dcc, Input, Output, State
import dash_bootstrap_components as dbc
import json
import hashlib
import datetime
import time
import boto3
from botocore.exceptions import ClientError
from dotenv import load_dotenv
import os
import logging
from secrets import token_urlsafe

# Load environment variables
load_dotenv()

# Initialize logging
logging.basicConfig(level=logging.INFO)

# Initialize the Dash application with responsive design
app = Dash(
    __name__,
    external_stylesheets=[dbc.themes.BOOTSTRAP],
    suppress_callback_exceptions=True,
)

# Token and session management
tokens = {}


def load_json(filename):
    try:
        with open(filename, "r") as file:
            return json.load(file)
    except FileNotFoundError:
        logging.error(f"File {filename} not found. Starting with an empty dataset.")
        return {} if filename.endswith(".json") else []


def save_json(filename, data):
    with open(filename, "w") as file:
        json.dump(data, file, indent=4)


def hash_secret(pin, salt):
    salted_pin = f"{salt}{pin}"
    return hashlib.sha256(salted_pin.encode("utf-8")).hexdigest()


def generate_and_save_token(email):
    token = token_urlsafe(16)
    user_details = load_json("users.json").get(email, {})
    tokens[token] = {
        "email": email,
        "token_created_at": int(time.time()),
        "apartment_number": user_details.get("apartment_number", "00"),
    }
    return token


def send_magic_link(email, token):
    ses_client = boto3.client("ses", region_name=os.getenv("AWS_REGION"))
    sender = os.getenv("AWS_SES_SENDER_EMAIL")
    subject = "Your Magic Link"
    body_html = f"""<html><body><h1>Your Magic Link</h1><p>Please use this link to access the app:</p><a href='http://localhost:8050?token={token}'>Access the App</a></body></html>"""
    try:
        response = ses_client.send_email(
            Destination={"ToAddresses": [email]},
            Message={
                "Body": {"Html": {"Charset": "UTF-8", "Data": body_html}},
                "Subject": {"Charset": "UTF-8", "Data": subject},
            },
            Source=sender,
        )
        return "Magic link sent! Check your email."
    except ClientError as e:
        logging.error(f"Failed to send email: {e}")
        return "Failed to send email."


app.layout = dbc.Container(
    [
        dcc.Location(id="url", refresh=False),
        html.Div(
            id="login-form",
            children=[
                dbc.Row(
                    dbc.Col(
                        html.Div(
                            [
                                html.H1(
                                    "Welcome to Your Smart Device Manager",
                                    className="text-center",
                                ),
                                html.P(
                                    "Manage your devices and security settings efficiently.",
                                    className="text-center",
                                ),
                            ]
                        ),
                        width=12,
                    )
                ),
                dbc.Row(
                    dbc.Col(
                        dbc.Form(
                            [
                                dbc.Input(
                                    id="email-input",
                                    placeholder="Enter your email",
                                    type="email",
                                    className="mb-2",
                                ),
                                dbc.Button(
                                    "Send Magic Link",
                                    id="send-link-btn",
                                    n_clicks=0,
                                    color="primary",
                                    className="me-1",
                                ),
                                html.Div(id="email-status"),
                            ]
                        ),
                        width=12,
                    )
                ),
            ],
        ),
        html.Div(
            id="auth-content",
            style={"display": "none"},
            children=[
                dbc.Alert(id="login-status", color="info", is_open=False),
                dbc.Card(
                    [
                        dbc.CardHeader("Device Registration"),
                        dbc.CardBody(
                            [
                                dbc.Input(
                                    id="mac-input",
                                    placeholder="Enter MAC address",
                                    type="text",
                                ),
                                dbc.Input(
                                    id="label-input",
                                    placeholder="Enter device label",
                                    type="text",
                                ),
                                dbc.Button(
                                    "Submit Device",
                                    id="submit-device-btn",
                                    n_clicks=0,
                                    color="success",
                                ),
                                html.Div(id="device-status"),
                            ]
                        ),
                        html.Div(id="device-status"),
                    ],
                    className="mb-3",
                ),
                dbc.Card(
                    [
                        dbc.CardHeader("PIN Registration"),
                        dbc.CardBody(
                            [
                                dbc.InputGroup(
                                    [
                                        dbc.InputGroupText(
                                            id="apartment-number", className="fw-bold"
                                        ),
                                        dbc.Input(
                                            id="pin-input",
                                            placeholder="Enter PIN",
                                            type="password",
                                        ),
                                    ]
                                ),
                                dbc.Button(
                                    "Submit PIN",
                                    id="submit-pin-btn",
                                    n_clicks=0,
                                    color="warning",
                                ),
                                html.Div(id="pin-status"),
                            ]
                        ),
                    ]
                ),
            ],
        ),
    ]
)


# Callbacks to handle user interactions and data processing
@app.callback(
    [Output("email-status", "children"), Output("login-form", "style")],
    [Input("send-link-btn", "n_clicks")],
    [State("email-input", "value")],
)
def handle_send_link(n_clicks, email):
    if n_clicks > 0 and email:
        token = generate_and_save_token(email)
        send_magic_link(email, token)
        return "Magic link sent! Check your email.", {"display": "none"}
    return "", {"display": "block"}


@app.callback(
    [
        Output("auth-content", "style"),
        Output("login-status", "children"),
        Output("login-status", "is_open"),
        Output("apartment-number", "children"),
    ],
    [Input("url", "search")],
    prevent_initial_call=True,
)
def manage_visibility(search):
    token = search.split("=")[1] if search else None
    if token and token in tokens:
        details = tokens[token]
        if (
            int(time.time()) - details["token_created_at"] < 3600
        ):  # Token expiration check
            return (
                {"display": "block"},
                f"Logged in as {details['email']}.",
                True,
                details["apartment_number"],
            )
        else:
            return {"display": "none"}, "Your magic link has expired.", True, ""
    return {"display": "none"}, "Invalid or expired token.", True, ""


# Device and PIN submission callbacks
@app.callback(
    Output("device-status", "children"),
    [Input("submit-device-btn", "n_clicks")],
    [
        State("mac-input", "value"),
        State("label-input", "value"),
        State("url", "search"),
    ],
)
def submit_device_data(n_clicks, mac, label, search):
    if n_clicks > 0:
        token = search.split("=")[1] if search else None
        if (
            token
            and token in tokens
            and int(time.time()) - tokens[token]["token_created_at"] < 3600
        ):
            devices = load_json("devices.json")
            devices.append(
                {
                    "label": label,
                    "owner": tokens[token]["email"],
                    "mac": mac,
                    "name": label,
                }
            )
            save_json("devices.json", devices)
            return "Device successfully registered."
        return "Session has expired. Please log in again."


@app.callback(
    Output("pin-status", "children"),
    [Input("submit-pin-btn", "n_clicks")],
    [State("pin-input", "value"), State("url", "search")],
)
def submit_pin_data(n_clicks, pin, search):
    if n_clicks > 0:
        token = search.split("=")[1] if search else None
        if (
            token
            and token in tokens
            and int(time.time()) - tokens[token]["token_created_at"] < 3600
        ):
            pins = load_json("pins.json")
            apartment_number = tokens[token]["apartment_number"]
            hashed_pin = hash_secret(pin, apartment_number)
            entry = {
                "hashed_pin": hashed_pin,
                "creator": tokens[token]["email"],
                "created_at": datetime.datetime.now().isoformat(),
            }
            if apartment_number in pins:
                pins[apartment_number].append(entry)
            else:
                pins[apartment_number] = [entry]
            save_json("pins.json", pins)
            return "PIN successfully registered."
        return "Session has expired. Please log in again."


if __name__ == "__main__":
    app.run_server(debug=True)
