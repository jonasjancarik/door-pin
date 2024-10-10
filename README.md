# door-pin

Simple door lock system with PIN codes, RFID tags and remote unlocking using Raspberry PI.

You can find the client web app under [door-control-web-app](https://github.com/jonasjancarik/door-control-web-app).

## Hardware

Works with the I/O Module from SÜDMETALL (https://www.suedmetall.com/products/locking-systems/stand-alone-solutions/i-o-modul/?lang=en). You have to set up wiring so that the PI sends a door unlocking signal by activating a relay on a 12-24 V circuit connected to the I/O module.

We're using GPIO pin number 18 - this is hardcoded in `utils.py`. 

## Install

```bash
python -m venv .venv
. .venv/bin/activate
pip install -r requirements.txt
```

If you encounter an error installing `evdev`, try installing the `python3-evdev` package with `sudo apt-get install python3-evdev`.

### Development

For development on a machine which doesn't support `RPi.GPIO` and `evdev`, run `grep -vE '^(RPi\.GPIO|evdev)' requirements.txt | pip install -r /dev/stdin` instead of the usual `pip install -r requirements.txt` to exclude these packages.

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

## Usage

### First-time setup

Run `python setup.py` to create the database and set up the first user. You can also use a CSV file with usernames and PIN codes to create multiple users at once - use the `users.csv.example` as a template.

### API and local listener

Launch the API server with `uvicorn api:app --reload` and the local PIN/RFID listener script with `python listen.py`.

### Management using the command-line interface

Use:

- `pin.py` for managing PIN codes
- `rfid.py` for managing RFID keytags or cards
