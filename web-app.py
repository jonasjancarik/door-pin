from dash import Dash, html, dcc, Input, Output, State, ctx
import dash_bootstrap_components as dbc
import boto3
from botocore.exceptions import ClientError
from dotenv import load_dotenv
import time
import os
import logging
from secrets import token_urlsafe
from flask import request
from pin import create_pin
from device import add_device
from utils import unlock_door, hash_secret, load_data, save_data

# Load environment variables
load_dotenv()

# Initialize logging
logging.basicConfig(level=logging.INFO)

# Initialize the Dash application with responsive design
app = Dash(
    __name__,
    external_stylesheets=[dbc.themes.BOOTSTRAP],
    suppress_callback_exceptions=True,
    meta_tags=[{"name": "viewport", "content": "width=device-width, initial-scale=1"}],
)


def generate_and_save_web_app_token(email, apartment_number):
    token_web = token_urlsafe(16)
    hashed_token = hash_secret(token_web)

    data = load_data()
    for user in data["apartments"][apartment_number]["users"]:
        if user["email"] == email:
            user_tokens = user.setdefault("tokens", [])
            user_tokens.append(
                {
                    "hash": hashed_token,
                    "expiration": int(time.time()) + 31536000,
                }  # 1 year expiration
            )
            break
    else:
        data["apartments"][apartment_number]["users"].append(
            {"email": email, "name": email, "token_hashes": [hashed_token]}
        )
    save_data(data)
    return token_web


def authenticate(search=None):
    token = get_token_from_url(search)
    cookie_token = request.cookies.get("web_app_token", None)
    token_to_use = (
        token or cookie_token
    )  # Use the token from the URL if present, prefer that over the cookie

    if not token_to_use:
        return False

    hashed_token = hash_secret(token_to_use)

    data = load_data()

    for apartment_number, apartment_data in data["apartments"].items():
        for user in apartment_data["users"]:
            for token in user.get("tokens", []):
                if token["hash"] == hashed_token and token["expiration"] > int(
                    time.time()
                ):
                    return {
                        "apartment_number": apartment_number,
                        "email": user["email"],
                        "name": user["name"],
                    }
    return False


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


# Define the app layout
app.layout = html.Div(
    [
        dcc.Location(id="url", refresh=False),
        dbc.Navbar(
            dbc.Container(
                [
                    dbc.Row(
                        [
                            dbc.Col(
                                dbc.NavbarBrand(
                                    os.getenv(
                                        "WEB_APP_TITLE", "House Access Control System"
                                    ),
                                    className="text-white",
                                )
                            ),
                        ],
                        align="center",
                        className="g-0",
                    ),
                    dbc.NavbarToggler(id="navbar-toggler"),
                    dbc.Collapse(
                        dbc.Nav(
                            [
                                dbc.NavItem(
                                    dbc.NavLink(
                                        os.getenv(
                                            "WEB_APP_SUBTITLE",
                                            "Manage your devices and security settings.",
                                        ),
                                        className="text-white",
                                    )
                                ),
                                dbc.NavItem(
                                    dbc.NavLink(
                                        "Settings",
                                        id="settings-btn",
                                        n_clicks=0,
                                        className="text-white",
                                        style={"cursor": "pointer"},
                                    )
                                ),
                                dbc.NavItem(
                                    dbc.NavLink(
                                        "Logout",
                                        id="logout-btn",
                                        n_clicks=0,
                                        className="text-white",
                                        style={"cursor": "pointer"},
                                    )
                                ),
                            ],
                            navbar=True,
                            className="ml-auto",
                        ),
                        id="navbar-collapse",
                        navbar=True,
                    ),
                ]
            ),
            color="dark",
            dark=True,
            sticky="top",
        ),
        dbc.Container(
            [
                dbc.Row(
                    [
                        dbc.Col(
                            [
                                html.Div(
                                    id="login-form",
                                    children=[
                                        dbc.Form(
                                            [
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
                                                    className="mb-2 w-100",
                                                    style={"cursor": "pointer"},
                                                ),
                                            ],
                                            className="d-flex flex-column align-items-center",
                                        ),
                                        html.Div(
                                            id="email-status",
                                            className="text-center mt-3",
                                        ),
                                    ],
                                    className="mt-5",
                                ),
                                html.Div(
                                    id="auth-content",
                                    style={"display": "none"},
                                    children=[
                                        dbc.Alert(
                                            id="login-status",
                                            color="info",
                                            is_open=False,
                                        ),
                                        dbc.Button(
                                            "Unlock Door",
                                            id="unlock-door-btn",
                                            color="danger",
                                            className="my-3 w-100",
                                            style={
                                                "width": "90%",
                                                "margin": "auto",
                                                "cursor": "pointer",
                                            },
                                        ),
                                        html.Div(id="unlock-status", className="mb-3"),
                                    ],
                                    className="mt-5",
                                ),
                            ],
                            width=12,
                            className="d-flex flex-column align-items-center justify-content-center",
                        )
                    ],
                    className="flex-grow-1",
                ),
                dbc.Modal(
                    [
                        dbc.ModalHeader("Settings"),
                        dbc.ModalBody(
                            [
                                html.H4("Device Registration", className="mb-3"),
                                dbc.Input(
                                    id="mac-input",
                                    placeholder="Enter MAC address",
                                    type="text",
                                    className="mb-2",
                                ),
                                dbc.Input(
                                    id="label-input",
                                    placeholder="Enter device label",
                                    type="text",
                                    className="mb-2",
                                ),
                                dbc.Button(
                                    "Submit Device",
                                    id="submit-device-btn",
                                    n_clicks=0,
                                    color="success",
                                    className="mb-4 w-100",
                                    style={"cursor": "pointer"},
                                ),
                                html.Div(id="device-status"),
                                html.H4("PIN Registration", className="mb-3"),
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
                                    ],
                                    className="mb-2",
                                ),
                                dbc.Button(
                                    "Submit PIN",
                                    id="submit-pin-btn",
                                    n_clicks=0,
                                    color="warning",
                                    className="w-100",
                                    style={"cursor": "pointer"},
                                ),
                                html.Div(id="pin-status"),
                            ]
                        ),
                        dbc.ModalFooter(
                            dbc.Button(
                                "Close",
                                id="close-settings-btn",
                                color="secondary",
                                n_clicks=0,
                                style={"cursor": "pointer"},
                            )
                        ),
                    ],
                    id="settings-modal",
                    is_open=False,
                    centered=True,
                    className="modal-lg",
                ),
                dcc.Store(id="dash_app_context", storage_type="session"),
            ],
            fluid=True,
            className="bg-light d-flex flex-column flex-grow-1",
        ),
    ],
    className="d-flex flex-column vh-100",
)


# Callbacks to handle user interactions and data processing
@app.callback(
    [Output("email-status", "children"), Output("login-form", "style")],
    [Input("send-link-btn", "n_clicks")],
    [State("email-input", "value")],
)
def handle_send_link(n_clicks, email):
    if n_clicks > 0 and email:
        data = load_data()
        for apartment_number, apartment_data in data["apartments"].items():
            for user in apartment_data["users"]:
                if user["email"] == email:
                    token = generate_and_save_web_app_token(email, apartment_number)
                    return send_magic_link(email, token), {"display": "none"}
        return "Email not found in the database.", {"display": "block"}
    return "", {"display": "block"}


def get_token_from_url(search):
    token = search.split("=")[1] if search else None
    return token if token != "logout" else None


@app.callback(
    [
        Output("auth-content", "style"),
        Output("login-form", "style", allow_duplicate=True),
        Output("login-status", "children"),
        Output("login-status", "is_open"),
        Output("login-status", "color"),
        Output("apartment-number", "children"),
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
            None,
        )
    else:
        if user := authenticate(search=search):
            return (
                {"display": "block"},
                {"display": "none"},
                f"Logged in as {user['name']}.",
                True,
                "info",
                user["apartment_number"],
                {
                    "web_app_token": get_token_from_url(search)
                    or request.cookies.get("web_app_token")
                },
            )

        return (
            {"display": "none"},
            {"display": "block"},
            "",
            False,
            "info",
            "",
            None,
        )


# Device and PIN submission callbacks
@app.callback(
    Output("pin-status", "children"),
    [Input("submit-pin-btn", "n_clicks")],
    [State("pin-input", "value"), State("url", "search")],
)
def submit_pin_data(n_clicks, pin, search):
    if n_clicks > 0:
        if user := authenticate(search):
            apartment_number = user["apartment_number"]
            creator_email = user["email"]
            label = (
                f"PIN {len(load_data()['apartments'][apartment_number]['pins']) + 1}"
            )
            create_pin(apartment_number, pin, creator_email, label)
            return "PIN successfully registered."
        return "Session has expired. Please log in again."


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
        if user := authenticate(search):
            apartment_number = user["apartment_number"]
            creator_email = user["email"]
            add_device(apartment_number, label, creator_email, mac)
            return "Device successfully registered."
        return "Session has expired. Please log in again."


@app.callback(
    Output("url", "href"),
    [Input("logout-btn", "n_clicks")],
    [State("url", "search")],
    prevent_initial_call=True,
)
def handle_logout(n_clicks, search):
    data = load_data()
    try:
        token_hashed = hash_secret(
            get_token_from_url(search) or request.cookies.get("web_app_token")
        )
    except ValueError:
        return "/"
    for apartment_number, apartment_data in data["apartments"].items():
        for user in apartment_data["users"]:
            for token in user.get("tokens", []):
                if token["hash"] == token_hashed:
                    user["tokens"].remove(token)
                    save_data(data)
                    break
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
    Output("settings-modal", "is_open"),
    [Input("settings-btn", "n_clicks"), Input("close-settings-btn", "n_clicks")],
    [State("settings-modal", "is_open")],
)
def toggle_settings_modal(open_clicks, close_clicks, is_open):
    if open_clicks or close_clicks:
        return not is_open
    return is_open


@app.callback(
    Output("navbar-collapse", "is_open"),
    [Input("navbar-toggler", "n_clicks")],
    [State("navbar-collapse", "is_open")],
)
def toggle_navbar(n_clicks, is_open):
    if n_clicks:
        return not is_open
    return is_open


@app.callback(
    Output("dash_app_context", "clear_data"),
    [Input("dash_app_context", "data")],
    [State("url", "search")],
    prevent_initial_call=True,
)
def set_cookie(response, search):
    token_web_user_supplied = get_token_from_url(search)
    if response:
        if token_web_user_supplied:
            ctx.response.set_cookie(
                "web_app_token", token_web_user_supplied, max_age=315360000
            )  # Set cookie to expire in 10 years
            return True  # Clear the data after setting the cookie
    return False  # No need to clear the data if response is None


if __name__ == "__main__":
    app.run_server(debug=True)
