from dash import Dash, html, dcc, Input, Output, State, ctx, ALL
import dash_bootstrap_components as dbc
from dotenv import load_dotenv
import time
import os
import logging
from pin import create_pin
from urllib.parse import parse_qs
import random
from dash_svg import Svg, Circle
import requests


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

app.title = os.getenv("WEB_APP_TITLE", "House Access Control System")


def random_index():
    return random.randint(0, 999999)


def exchange_code_for_token(login_code):
    try:
        response = requests.post(
            f"{os.getenv('API_URL')}/exchange-code",
            json={"login_code": str(login_code)},
            # data=str(login_code),
        )
    except requests.exceptions.ConnectionError:
        logging.error("Failed to connect to the API.")
        return None
    if response.status_code == 200:
        return response.json()
    else:
        if json_response := response.json():
            logging.error(f"Failed to exchange code: {json_response}")
        else:
            logging.error(f"Failed to exchange code: {response.text}")
    return None


def authenticate(token=None):
    response = requests.post(
        f"{os.getenv('API_URL')}/authenticate",
        headers={"Authorization": f"Bearer {token}"},
    )
    if response.status_code == 200:
        return response.json()["user"]


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
                                html.Div(
                                    dbc.NavItem(
                                        dbc.NavLink(
                                            "Settings",
                                            id="settings-btn",
                                            n_clicks=0,
                                            className="text-white",
                                            style={"cursor": "pointer"},
                                        ),
                                    ),
                                    className="show-logged-in d-none",
                                    id={
                                        "type": "toggle-element",
                                        "index": random_index(),
                                    },
                                ),
                                html.Div(
                                    dbc.NavItem(
                                        dbc.NavLink(
                                            id="user-display", className="text-white"
                                        )
                                    ),
                                    className="show-logged-in d-none",
                                    id={
                                        "type": "toggle-element",
                                        "index": random_index(),
                                    },
                                ),
                                html.Div(
                                    dbc.NavItem(
                                        dbc.NavLink(
                                            "(Logout)",
                                            id="logout-btn",
                                            n_clicks=0,
                                            className="text-white",
                                            style={"cursor": "pointer"},
                                        )
                                    ),
                                    className="show-logged-in d-none",
                                    id={
                                        "type": "toggle-element",
                                        "index": random_index(),
                                    },
                                ),
                            ],
                            navbar=True,
                            className="ms-auto",
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
                            children=[
                                html.Div(
                                    id="login-form",
                                    className="w-100",
                                    children=[
                                        html.Div(
                                            id="email-form",
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
                                                            "Send Login Code",
                                                            id="send-link-btn",
                                                            n_clicks=0,
                                                            color="secondary",
                                                            outline=True,
                                                            className="mb-2 w-100",
                                                            style={"cursor": "pointer"},
                                                        ),
                                                    ],
                                                    className="d-flex flex-column align-items-center",
                                                ),
                                            ],
                                        ),
                                        html.Div(
                                            id="code-form",
                                            children=[
                                                html.Div(
                                                    id="email-status",
                                                    className="text-center",
                                                ),
                                                dbc.Form(
                                                    [
                                                        dbc.Input(
                                                            id="login-code-input",
                                                            placeholder="Enter login code",
                                                            type="text",
                                                            className="mb-2 text-center",
                                                        ),
                                                    ],
                                                    className="d-flex flex-column align-items-center mt-3",
                                                ),
                                            ],
                                        ),
                                    ],
                                ),
                            ],
                            className="d-flex flex-column align-items-center justify-content-center col-sm-10 col-lg-4 col-xl-4 mx-auto",
                        )
                    ],
                    className="flex-grow-1 show-logged-out d-none",
                    id={
                        "type": "toggle-element",
                        "index": random_index(),
                    },
                ),
                dbc.Row(
                    dbc.Col(
                        html.Div(
                            children=[
                                html.Button(
                                    "Unlock Door",
                                    id="unlock-door-btn",
                                    className="button-round",
                                ),
                                Svg(
                                    Circle(
                                        cx="60",
                                        cy="60",
                                        r="58",  # perfectly inset from the edge of the round button
                                        fill="none",
                                        stroke="#343434",
                                        strokeWidth="4",
                                        strokeDasharray="364.424",  # 2 * pi * r
                                        strokeDashoffset="0",
                                        id="countdown-circle",
                                    ),
                                    viewBox="0 0 120 120",
                                    className="svg-circle",
                                    id="svg-circle",
                                ),
                                html.Div(id="unlock-status", hidden=True),
                            ],
                            id="unlock-button-container",
                            style={
                                "position": "relative",
                                "display": "inline-block",
                            },
                        ),
                        className="d-flex flex-column align-items-center justify-content-center",
                    ),
                    id={"type": "toggle-element", "index": random_index()},
                    className="toggle-element show-logged-in d-none flex-grow-1",
                ),
                html.Div(
                    dbc.Modal(
                        [
                            dbc.ModalHeader("Settings"),
                            dbc.ModalBody(
                                [
                                    # User adding
                                    html.H4("User Registration", className="mb-3"),
                                    dbc.Input(
                                        id="user-email-input",
                                        placeholder="Enter user email",
                                        type="email",
                                        className="mb-2",
                                    ),
                                    dbc.Input(
                                        id="user-name-input",
                                        placeholder="Enter user name",
                                        type="text",
                                        className="mb-2",
                                    ),
                                    # checkbox whether the user is a guest -explain that guests cannot add other users but can set PINs
                                    dbc.Checkbox(
                                        id="user-guest-checkbox",
                                        className="mb-2",
                                        label="Guest (won't be able to add other users)",
                                    ),
                                    dbc.Button(
                                        "Add User",
                                        id="submit-user-btn",
                                        n_clicks=0,
                                        color="primary",
                                        className="w-100",
                                        style={"cursor": "pointer"},
                                    ),
                                    html.Div(id="user-status"),
                                    html.H4("PIN Registration", className="mb-3 mt-2"),
                                    dbc.Input(
                                        id="pin-input",
                                        placeholder="Enter 4-digit PIN",
                                        type="password",
                                        className="mb-2",
                                    ),
                                    dbc.Input(
                                        id="label-input",
                                        placeholder="Enter PIN label",
                                        type="text",
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
                    className="toggle-element show-logged-in d-none",
                    id={"type": "toggle-element", "index": random_index()},
                ),
            ],
            fluid=True,
            id="content-wrapper",
            className="d-flex flex-column flex-grow-1",
        ),
        # Hidden input to trigger callback on page load
        dcc.Input(id="page-load-trigger", type="hidden", value="trigger"),
        # Stores
        dcc.Store(
            id="dash_app_context", storage_type="local"
        ),  # todo: choose better name
        dcc.Store(id="authenticated", storage_type="local"),
        dcc.Store(id="login-stage", storage_type="session", data="email-form"),
    ],
    className="d-flex flex-column vh-100",
)


# Callbacks to handle user interactions and data processing
@app.callback(
    [
        Output("email-status", "children"),
        Output("email-form", "style"),
        Output("code-form", "style"),
    ],
    [Input("send-link-btn", "n_clicks")],
    [State("email-input", "value")],
)
def handle_send_link(n_clicks, email):
    if n_clicks > 0 and email:
        try:
            response = requests.post(
                os.getenv("API_URL") + "/send-magic-link", json={"email": email}
            )
        except requests.exceptions.ConnectionError:
            logging.error("Failed to connect to the API.")
            return (
                "Failed to connect to the API.",
                {"display": "block"},
                {"display": "none"},
            )
        if response.status_code != 200:
            return "Failed to send email.", {"display": "block"}, {"display": "none"}
        else:
            return (
                "A login code has been sent to your email. Please enter the code below or click the link in the email.",
                {"display": "none"},
                {"display": "block"},
            )
    return "", {"display": "block"}, {"display": "none"}


def get_login_code_from_url(search):
    if not search:
        return None

    query_params = parse_qs(search.lstrip("?"))
    login_code = query_params.get("login_code", [None])[0]
    return login_code if login_code != "logout" else None


# Callback to show/hide elements based on login state using pattern-matching
@app.callback(
    Output({"type": "toggle-element", "index": ALL}, "className"),
    [Input("authenticated", "data"), Input("page-load-trigger", "value")],
    [
        State({"type": "toggle-element", "index": ALL}, "id"),
        State({"type": "toggle-element", "index": ALL}, "className"),
    ],
)
def update_element_visibility(authenticated, trigger, ids, current_classes):
    updated_classes = []
    for i, element_id in enumerate(ids):
        if (
            current_classes[i] is None
        ):  # this shouldn't happen because the element should have a class defining whether it should be shown or hidden
            current_classes[i] = ""

        class_to_add = None

        # update the class list based on the login state and display class
        if "show-logged-in" in current_classes[i]:
            if authenticated:
                # remove d-none from the class list
                current_classes[i] = current_classes[i].replace("d-none", "")
            else:
                class_to_add = "d-none"

        elif "show-logged-out" in current_classes[i]:
            if not authenticated:
                # remove d-none from the class list
                current_classes[i] = current_classes[i].replace("d-none", "")
            else:
                class_to_add = "d-none"

        else:
            updated_classes.append(current_classes[i])
            continue

        if class_to_add and class_to_add not in current_classes[i]:
            updated_classes.append(current_classes[i] + " " + class_to_add)
        else:
            updated_classes.append(current_classes[i])

    return updated_classes


@app.callback(
    Output("user-display", "children"),
    Input("authenticated", "data"),
    State("dash_app_context", "data"),
)
def update_login_state(is_authenticated, dash_app_context):
    if is_authenticated:
        return dash_app_context["user"]["name"]
    else:
        return ""


@app.callback(
    Output("login-stage", "data"),
    [Input("send-link-btn", "n_clicks"), Input("login-code-input", "n_submit")],
    [State("login-stage", "data")],
)
def update_login_stage(send_link_clicks, code_input_submit, current_stage):
    if send_link_clicks and current_stage == "email-form":
        return "code-form"
    if code_input_submit and current_stage == "code-form":
        return "authenticated"
    return current_stage


@app.callback(
    [
        Output("authenticated", "data"),
        Output("dash_app_context", "data"),
    ],
    [
        Input("url", "search"),
        Input("logout-btn", "n_clicks"),
        Input("login-code-input", "value"),
        Input("dash_app_context", "data"),
    ],
)
def handle_login(search, n_clicks, login_code_input, dash_app_context):
    triggered_id = ctx.triggered[0]["prop_id"].split(".")[0]

    if triggered_id == "logout-btn" and n_clicks or search == "?token=logout":
        return (
            False,
            {"web_app_token": None},
        )
    else:
        login_code_from_url = parse_qs(search.lstrip("?")).get("login_code", [None])[
            0
        ]  # todo: we have a function for that - which can maybe be replaced by this
        login_code_entered = login_code_input
        login_code = login_code_entered or login_code_from_url
        web_app_token = (
            dash_app_context.get("web_app_token") if dash_app_context else None
        )

        if not web_app_token and login_code and login_code != "logout":
            if response := exchange_code_for_token(login_code):
                return (
                    True,
                    {
                        "web_app_token": response["access_token"],
                        "user": response["user"],
                    },
                )
            else:
                return (
                    False,
                    {"web_app_token": None},
                )
        elif web_app_token:
            if user := authenticate(web_app_token):
                return (
                    True,
                    {
                        "web_app_token": web_app_token,
                        "user": user,
                    },
                )
        else:  # edge case - no token and no login code
            return (
                False,
                {"web_app_token": None},
            )


# Device and PIN submission callbacks
@app.callback(
    Output("pin-status", "children"),
    [Input("submit-pin-btn", "n_clicks")],
    [
        State("pin-input", "value"),
        State("label-input", "value"),
        State("dash_app_context", "data"),
    ],
)
def submit_pin_data(n_clicks, pin, label, dash_app_context):
    if n_clicks > 0:
        if pin and len(pin) == 4 and pin.isdigit():
            # check if PIN is not insecure
            if pin in [
                "1234",
                "0000",
                "1111",
                "2222",
                "3333",
                "4444",
                "5555",
                "6666",
                "7777",
                "8888",
                "9999",
            ]:
                return "This PIN is not secure. PINs like 1234 or 1111 are not allowed. Please choose a different one."
            if user := authenticate(web_app_token=dash_app_context["web_app_token"]):
                apartment_number = user["apartment_number"]
                creator_email = user["email"]
                if not label:
                    label = time.strftime("%Y-%m-%d %H:%M:%S")
                create_pin(apartment_number, pin, creator_email, label)
                return "PIN successfully registered."
            return "Session has expired. Please log in again."
        else:
            if not pin:
                return "Please enter a 4-digit PIN."
            if not pin.isdigit():
                return "PIN must be a 4-digit number."
            if len(pin) != 4:
                if len(pin) < 4:
                    return "PIN is too short. Please enter a 4-digit number."
                if len(pin) > 4:
                    return "PIN is too long. Please enter a 4-digit number."


# Callback to add a user
@app.callback(
    Output("user-status", "children"),
    [Input("submit-user-btn", "n_clicks")],
    [
        State("user-email-input", "value"),
        State("user-name-input", "value"),
        State("user-guest-checkbox", "value"),
        State("dash_app_context", "data"),
    ],
)
def add_user(n_clicks, email, name, is_guest, dash_app_context):
    if n_clicks > 0:
        if not email:
            return "Please enter an email address."

        new_user = {"email": email, "name": name if name else email, "guest": is_guest}
        try:
            response = requests.post(
                f"{os.getenv('API_URL')}/user/create",
                json=new_user,
                headers={
                    "Authorization": f"Bearer {dash_app_context["web_app_token"]}"
                },
            )
        except requests.exceptions.ConnectionError:
            logging.error("Failed to connect to the API.")
            return "Failed to connect to the API."
        except (
            requests.exceptions.HTTPError
        ) as e:  # todo: what exactly does this catch if not error status codes?
            logging.error(f"Failed to add user: {e}")
            return "Failed to add user."

        if response.status_code != 200:
            if (
                response.status_code == 403
                and response.json().get("detail") == "Guests cannot create users"
            ):
                return "Guests cannot create users."  # todo: don't show the option to add users to guests
            elif response.status_code == 409:
                return "User already exists."
            else:
                return "Failed to add user."

        return "User added."
        # return "Session has expired. Please log in again."


@app.callback(
    [
        Output("url", "href"),
        Output("authenticated", "data", allow_duplicate=True),
        Output("dash_app_context", "data", allow_duplicate=True),
    ],
    [Input("logout-btn", "n_clicks")],
    [State("url", "search")],
    prevent_initial_call=True,
)
def handle_logout(n_clicks, search):
    try:
        requests.post(os.getenv("API_URL") + "/logout")
    except requests.exceptions.ConnectionError:
        logging.error("Failed to connect to the API.")
    except requests.exceptions.HTTPError as e:
        logging.error(f"Failed to log out: {e}")
    except requests.exceptions.RequestException as e:
        # This will capture general request-related errors, including invalid responses
        logging.error(f"An error occurred: {e}")

    return "/?token=logout", False, {"web_app_token": None}


@app.callback(
    [
        Output("unlock-status", "children", allow_duplicate=True),
        Output("unlock-door-btn", "disabled", allow_duplicate=True),
        Output("unlock-door-btn", "children", allow_duplicate=True),
        Output("countdown-circle", "style", allow_duplicate=True),
    ],
    [Input("unlock-door-btn", "n_clicks")],
    prevent_initial_call=True,
)
def handle_unlock_door(n_clicks):
    return (
        "unlocking",
        True,
        "Unlocked...",
        {
            "transition": "stroke-dashoffset 7s linear",
            "strokeDashoffset": "364.424",  # This makes the stroke disappear
        },
    )


@app.callback(
    [
        Output("unlock-door-btn", "disabled"),
        Output("unlock-door-btn", "children"),
        Output("unlock-status", "children"),
        Output("authenticated", "data", allow_duplicate=True),
        Output("countdown-circle", "style", allow_duplicate=True),
    ],
    [Input("unlock-status", "children")],
    State("dash_app_context", "data"),
    prevent_initial_call=True,
)
def toggle_unlock_button(unlock_status, dash_app_context):
    if unlock_status == "unlocking":
        token = dash_app_context["web_app_token"]
        try:
            response = requests.post(
                f"{os.getenv('API_URL')}/unlock",
                headers={"Authorization": f"Bearer {token}"},
            )
        except requests.exceptions.ConnectionError:
            logging.error("Failed to connect to the lock.")
            return (
                True,  # Keep button disabled
                "Failed to unlock door - couldn't connect to the lock.",  # Change button text to indicate failure
                "Failed",  # Error message
                False,  # Authentication status
                {
                    "transition": "stroke-dashoffset 0.5s linear",
                    "strokeDashoffset": "0",  # This resets the stroke quickly
                },
            )
        if response.status_code == 200:
            time.sleep(7)  # The lock stays open for 7 seconds
            # Animation for the SVG circle
            return (
                False,  # Button disabled
                "Unlock Door",  # Button text
                "Door unlocked",  # Status message
                True,  # Authentication status
                {
                    "transition": "stroke-dashoffset 0.5s linear",
                    "strokeDashoffset": "0",  # This resets the stroke quickly
                },
            )
        elif response.status_code == 401:
            return (
                True,  # Keep button disabled
                "Log in again to unlock door.",  # Change button text to indicate re-login
                "Session expired, please log in again.",  # Error message
                False,  # Authentication status
                {
                    "transition": "stroke-dashoffset 0.5s linear",
                    "strokeDashoffset": "0",  # This resets the stroke quickly
                },
            )
        else:
            return (
                True,  # Keep button disabled
                "Failed to unlock door.",  # Change button text to indicate failure
                "Failed",  # Error message
                True,  # Authentication status
                {
                    "transition": "stroke-dashoffset 0.5s linear",
                    "strokeDashoffset": "0",  # This resets the stroke quickly
                },
            )


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


if __name__ == "__main__":
    app.run_server(debug=True, port=os.getenv("WEB_APP_PORT", 8050))
