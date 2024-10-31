# door-pin

Simple door lock system with PIN codes, RFID tags and remote unlocking using Raspberry PI.

You can find the client web app under [door-control-web-app](https://github.com/jonasjancarik/door-control-web-app).

## Hardware

Tested on Raspberry PI 4 and 5. On Raspberry PI 3, you will have trouble installing the required packages (in particular rpi-gpio) with Python 3.11. The code contains some async stuff that won't work on Python 3.9 (which is the default on Raspberry PI 3) and rpi.gpio won't run on Python 3.11 on Raspberry PI 3 (`version `GLIBC_2.34' not found`).

This will work with any relay operated lock that you can control from the GPIO pins of a Raspberry PI. You have to set up wiring so that the PI sends a door unlocking signal by activating a relay on a 12-24 V circuit connected to the I/O module. Tested with the I/O Module from SÜDMETALL (https://www.suedmetall.com/products/locking-systems/stand-alone-solutions/i-o-modul/?lang=en).

By default, the code expects the relay to be connected to GPIO pin 18, but this can be changed by setting the `RELAY_PIN` environment variable.

## Install

```bash
python -m venv .venv
. .venv/bin/activate
pip install --upgrade pip
pip install -r requirements.txt
```

If you encounter an error installing `evdev`, try installing the `python3-evdev` package with `sudo apt-get install python3-evdev`. In that case you may want to create the virtual environment with the `--system-site-packages` flag (i.e. `python -m venv .venv --system-site-packages`) and ignore the `evdev` package in the `requirements.txt` file with `grep -v "evdev" requirements.txt | pip install -r /dev/stdin`.

If you want to get the latest versions of all the required packages, you can try running `pip install fastapi sqlalchemy boto3 python-dotenv uvicorn "pydantic[email]" rpi-lgpio evdev` directly.

### Development

For development on a machine which doesn't support `RPi.GPIO` and `evdev`, run just `pip install fastapi sqlalchemy boto3 python-dotenv uvicorn "pydantic[email]"` to exclude these packages.

Then create a `RPi` package with a dummy `GPIO` module to avoid errors:

```bash
mkdir RPi
touch RPI/__init__.py
touch RPi/GPIO.py
```

and add the following code to `RPi/GPIO.py`:

```python
def setmode(a):
    print(a)


def setup(a, b):
    print(a)


def output(a, b):
    print(a)


def cleanup():
    print("a")


def setwarnings(flag):
    print("False")


def LOW():
    print("LOW")


def HIGH():
    print("HIGH")


def BCM():
    print("BCM")


def OUT():
    print("OUT")
```

## Networking

Because this will be running on a Raspberry PI - likely without a static public IP address or port forwarding, use another server as a proxy to forward requests to the Raspberry PI.

On the Raspberry PI, set up reverse port forwarding like this:

```bash
ssh -R 8000:localhost:8000 <server>
```

Or use autossh to keep the connection alive, for example:

```bash
autossh -M 20000 -N -R 8000:localhost:8000 username@proxy-server -o "ServerAliveInterval 30" -o "ServerAliveCountMax 3"
```

You can even set it up as a systemd service to run in the background like this:

```bash
[Unit]
Description=AutoSSH tunnel service for port 4444
After=network.target

[Service]
User=pi
Group=pi
ExecStart=/usr/bin/autossh -M 20000 -N -R 8000:localhost:8000 username@proxy-server -o "ServerAliveInterval 30" -o "ServerAliveCountMax 3"
Restart=always
RestartSec=3
StartLimitIntervalSec=60
StartLimitBurst=10

[Install]
WantedBy=multi-user.target
```

## Usage

### First-time setup

Run `python setup.py` to create the database and set up the first user. You can also use a CSV file with usernames and PIN codes to create multiple users at once - use the `users.csv.example` as a template.

### Launching the API server

Launch the API server with `uvicorn api:app` (or with the `--reload` flag for development). 

You need to obtain a bearer token first to use the API directly - you can do it through the web app and extracting the bearer token from the `Authorization` header of the requests. There is functionality for proper API keys in the API, but it is not tested and implemented in the frontend client app yet.
