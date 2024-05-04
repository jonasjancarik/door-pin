# door-pin

Simple door lock system with PIN codes (entered using a USB numeric keyboard) and remote unlocking, using Raspberry PI.

## Hardware

Works with the I/O Module from SÜDMETALL (https://www.suedmetall.com/products/locking-systems/stand-alone-solutions/i-o-modul/?lang=en). You have to set up wiring so that the PI sends a door unlocking signal by activating a relay on a 12-24 V circuit connected to the I/O module.

We're using GPIO pin number 18 - this is hardcoded in `utils.py`. 

## Install

```bash
python -m venv .venv
. .venv/bin/activate
pip install -r requirements.txt
```

## Networking

Because this will be running on a Raspberry PI - likely without a static public IP address or port forwarding, use another server as a proxy to forward requests to the Raspberry PI.

On the Raspberry PI, set up reverse port forwarding like this:

```bash
ssh -R 8000:localhost:8000 <server>
```

## Usage

### User management

Scripts:
- `pin.py` for managing PIN codes
- `tokens.py` for managing tokens (URL credentials for remote unlocking)

### Remote unlocking

Run the API server with `uvicorn api:app --reload` for remote unlocking.

Users that have a token can unlock the door by visiting the URL `http://<server>:8000/door/unlock?username=<username>&token=<token>`.
