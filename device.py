import utils
import json
import sys

bt = utils.Bluetoothctl()


def load_devices():
    """Load device data from the JSON file."""
    try:
        with open("devices.json", "r") as file:
            return json.load(file)
    except FileNotFoundError:
        return []


def save_devices(devices):
    """Save device data to the JSON file."""
    with open("devices.json", "w") as file:
        json.dump(devices, file, indent=4)


def add_device(label, owner, mac):
    """Add a new device."""
    devices = load_devices()
    devices.append(
        {
            "label": label,
            "owner": owner,
            "mac": mac,
        }
    )
    save_devices(devices)
    print("Device added successfully.")


def remove_device(mac):
    """Remove a device by its MAC address."""
    devices = load_devices()
    updated_devices = [device for device in devices if device["mac"] != mac]
    if len(updated_devices) < len(devices):
        save_devices(updated_devices)
        print("Device removed successfully.")
    else:
        print("Device not found.")


def list_devices():
    """List all registered devices."""
    devices = load_devices()
    for device in devices:
        print(
            f"Label: {device['label']}, Owner: {device['owner']}, MAC: {device['mac']}"
        )


def add_paired():
    paired_devices = bt.list_paired_devices()

    if not paired_devices:
        print("No paired devices found.")
        sys.exit()
    else:
        print("Paired devices:")
        for idx, mac in enumerate(paired_devices):
            print(f"{idx + 1}: {mac}")

            choice = input("Enter the number of the device to add: ")

            try:
                choice = int(choice)
            except ValueError:
                print("Invalid selection. Exiting.")
                sys.exit()

            device = paired_devices[choice - 1]

            label = input("Label: ")
            owner = input("Owner: ")

            # write info to paired devices json file
            approved_devices = utils.get_approved_devices()

            approved_devices.append(
                {
                    "label": label,
                    "owner": owner,
                    "mac": device["mac"],
                    "name": device["name"],
                }
            )

            with open("devices.json", "w") as f:
                json.dump(approved_devices, f, ensure_ascii=False, indent=4)

            print("Device added successfully.")


def add_without_pairing():
    mac = input("Enter the MAC address of the device: ")
    label = input("Label: ")
    owner = input("Owner: ")

    # write info to paired devices json file
    approved_devices = utils.get_approved_devices()

    approved_devices.append(
        {
            "label": label,
            "owner": owner,
            "mac": mac,
        }
    )

    with open("devices.json", "w") as f:
        json.dump(approved_devices, f, ensure_ascii=False, indent=4)

    print("Device added successfully.")


def list_or_remove():
    approved_devices = utils.get_approved_devices()

    if not approved_devices:
        sys.exit("No approved devices found. Exiting.")

    print("Approved devices:")
    for idx, device in enumerate(approved_devices):
        print(f"{idx + 1}: {device['owner']}'s {device['label']} ({device['mac']})")

    choice = input("Enter the number of the device to remove (empty to skip): ")

    if not choice:
        sys.exit()

    try:
        choice = int(choice)
    except ValueError:
        print("Invalid selection. Exiting.")
        sys.exit()

    approved_devices.pop(choice - 1)

    with open("devices.json", "w") as f:
        json.dump(approved_devices, f, ensure_ascii=False, indent=4)

    print("Device removed successfully.")


def main():
    # ask user what they want to do:
    print("Select task: ")
    print("1. Add a paired device")
    print("2. Add a device without pairing")
    print("3. List or remove devices")

    task = input("Enter the number of the task: ")

    if task == "1":
        add_paired()
    elif task == "2":
        add_without_pairing()
    elif task == "3":
        list_or_remove()
    else:
        print("Invalid task number. Exiting.")
        sys.exit()


if __name__ == "__main__":
    main()
