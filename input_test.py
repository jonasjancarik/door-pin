import evdev
from select import select

# Find all input devices
devices = [evdev.InputDevice(path) for path in evdev.list_devices()]
device_dict = {dev.fd: dev for dev in devices}

# Display detected devices
print("Monitoring the following devices:")
for device in devices:
    print(f"{device.path}: {device.name}")

# Monitor all devices for events
while True:
    r, w, x = select(device_dict, [], [])
    for fd in r:
        device = device_dict[fd]
        for event in device.read():
            if event.type == evdev.ecodes.EV_KEY:
                key_event = evdev.categorize(event)
                if key_event.keystate == evdev.KeyEvent.key_down:
                    print(f"Key pressed on {device.name}: {key_event.keycode}")
