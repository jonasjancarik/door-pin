from dash import Dash, html, dcc, Input, Output, State, ctx
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
from flask import request

try:
    from utils import unlock_door
except ImportError:

    def unlock_door():
        print("Door unlocked successfully.")


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


def hash_secret(username, token):
    salted_token = f"{username}{token}"
    return hashlib.sha256(salted_token.encode("utf-8")).hexdigest()


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


def generate_and_save_web_app_token(email):
    token_web = token_urlsafe(16)
    user_details = load_json("users.json").get(email, {})
    tokens[hash_secret("", token_web)] = {
        "email": email,
        "token_created_at": int(time.time()),
        "apartment_number": user_details.get("apartment_number", "00"),
    }
    return token_web


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
        print(f"Email sent! {response}")
        return "Magic link sent! Check your email and click the link to log in."
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
                                    os.getenv(
                                        "WEB_APP_TITLE", "House Access Control System"
                                    ),
                                    className="text-center",
                                ),
                                html.P(
                                    os.getenv(
                                        "WEB_APP_SUBTITLE",
                                        "Manage your devices and security settings.",
                                    ),
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
                            children=[
                                dbc.Input(
                                    id="email-input",
                                    placeholder="Enter your email",
                                    type="email",
                                    className="mb-2 text-center",
                                ),
                                dbc.Button(
                                    "Send Magic Link",
                                    id="send-link-btn",
                                    n_clicks=0,
                                    color="primary",
                                    className="me-1",
                                ),
                            ],
                            className="d-flex flex-column align-items-center",
                        ),
                        width=3,
                    ),
                    # align the form to the center
                    className="d-flex justify-content-center",
                ),
            ],
        ),
        html.Div(id="email-status", className="text-center mt-5"),
        html.Div(
            id="auth-content",
            style={"display": "none"},
            className="mt-5",
            children=[
                dbc.Alert(id="login-status", color="info", is_open=False),
                dbc.Button(
                    "Unlock Door",
                    id="unlock-door-btn",
                    color="danger",
                    className="mb-3",
                ),
                dbc.Button(
                    "Settings", id="settings-btn", color="primary", className="mb-3"
                ),
                dbc.Button(
                    "Logout", id="logout-btn", color="secondary", className="mb-3"
                ),
                html.Div(id="unlock-status", className="mb-3"),
                html.Div(
                    id="settings-content",
                    style={"display": "none"},
                    children=[
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
                                                    id="apartment-number",
                                                    className="fw-bold",
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
            ],
        ),
        dcc.Store(id="dash_app_context", storage_type="session"),
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
        # load users from the JSON file
        users = load_json("users.json")
        if email not in users:
            return "Email not found in the database.", {"display": "block"}
        token = generate_and_save_web_app_token(email)
        return send_magic_link(email, token), {"display": "none"}
    return "", {"display": "block"}


def get_token_from_url(search):
    token = search.split("=")[1] if search else None
    return token if token != "logout" else None


def get_hashed_token(token):
    return hash_secret("", token) if token else None


@app.callback(
    [
        Output("auth-content", "style"),
        Output("login-form", "style", allow_duplicate=True),
        Output("login-status", "children"),
        Output("login-status", "is_open"),
        Output("login-status", "color"),
        Output("apartment-number", "children"),
        Output("settings-content", "style", allow_duplicate=True),
        Output("dash_app_context", "data"),
    ],
    [Input("url", "search"), Input("logout-btn", "n_clicks")],
    [State("url", "pathname")],
    prevent_initial_call=True,
)
def manage_visibility(search, n_clicks, pathname):
    triggered_id = ctx.triggered[0]["prop_id"].split(".")[0]

    if triggered_id == "logout-btn" and n_clicks:
        return (
            {"display": "none"},
            {"display": "block"},
            "You have been logged out.",
            True,
            "success",
            "",
            {"display": "none"},
            None,
        )
    else:
        token_web_user_supplied = get_token_from_url(search)
        token_web_user_supplied_hashed = get_hashed_token(token_web_user_supplied)
        cookie_token = request.cookies.get("web_app_token", None)
        cookie_token_hashed = get_hashed_token(cookie_token)

        token_to_use = (
            token_web_user_supplied_hashed
            if token_web_user_supplied_hashed in tokens
            else cookie_token_hashed
        )

        if token_to_use and token_to_use in tokens:
            user_token_info = tokens[token_to_use]
            response = {"web_app_token": token_web_user_supplied}
            return (
                {"display": "block"},
                {"display": "none"},
                f"Logged in as {user_token_info['email']}.",
                True,
                "info",
                user_token_info["apartment_number"],
                {"display": "none"},
                response,
            )
        else:
            return (
                {"display": "none"},
                {"display": "block"},
                "",
                False,
                "info",
                "",
                {"display": "none"},
                None,
            )


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
        if token and token in tokens:
            devices = load_json("devices.json")
            if not devices:
                devices = []
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
        if token and token in tokens:
            pins = load_json("pins.json")
            if not pins:
                pins = {}
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


@app.callback(
    Output("url", "href"),
    [Input("logout-btn", "n_clicks")],
    [State("url", "search")],
    prevent_initial_call=True,
)
def handle_logout(n_clicks, search):
    token = search.split("=")[1] if search else None
    if token:
        token_hashed = hash_secret("", token)
        if token_hashed in tokens:
            del tokens[token_hashed]
    ctx.response.delete_cookie("web_app_token")
    return "/?token=logout"


@app.callback(
    Output("unlock-status", "children"),
    [Input("unlock-door-btn", "n_clicks")],
    prevent_initial_call=True,
)
def handle_unlock_door(n_clicks):
    if n_clicks > 0:
        try:
            unlock_door()
            return "Door unlocked successfully."
        except Exception as e:
            return f"Error unlocking door: {str(e)}"


@app.callback(
    Output("settings-content", "style"),
    [Input("settings-btn", "n_clicks")],
    [State("settings-content", "style")],
)
def toggle_settings(n_clicks, current_style):
    if n_clicks:
        if current_style["display"] == "none":
            return {"display": "block"}
        else:
            return {"display": "none"}
    return current_style


@app.callback(
    Output("dash_app_context", "clear_data"),
    [Input("dash_app_context", "data")],
    prevent_initial_call=True,
)
def set_cookie(response):
    if response:
        token_web_user_supplied = response.get("web_app_token")
        if token_web_user_supplied:
            ctx.response.set_cookie(
                "web_app_token", token_web_user_supplied, max_age=315360000
            )  # Set cookie to expire in 10 years
            return True  # Clear the data after setting the cookie
    return False  # No need to clear the data if response is None


if __name__ == "__main__":
    app.run_server(debug=True)
