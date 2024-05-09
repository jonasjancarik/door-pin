import utils
import json


def main():
    print("Initializing Bluetooth...")
    bl = utils.Bluetoothctl()
    scan_duration = 5

    choice = 0

    while choice == 0:
        bl.scan(scan_duration)

        devices = bl.list_devices()
        if not devices:
            print("No devices found.")
            return

        print("Available devices:")

        for idx, (mac, name) in enumerate(devices):
            print(f"{idx + 1}: {name} ({mac})")

        choice = input("Enter the number of the device to pair (0 to scan again): ")

        try:
            choice = int(choice)
        except ValueError:
            print("Invalid selection. Scanning again...")
            choice = 0

        scan_duration += 5

    try:
        device_selected = devices[int(choice) - 1]
        device_to_pair = {
            "name": device_selected[1] if device_selected[0] != "Device" else None,
            "mac": device_selected[0]
            if device_selected[0] != "Device"
            else device_selected[1].split(" ")[0],
        }

        success = bl.pair_device(device_to_pair["mac"])

        if success:
            print("Device paired successfully.")
        else:
            print("Failed to pair device.")

        label = input("Label: ")
        owner = input("Owner: ")

        # write info to paired devices json file
        try:
            approved_devices = json.load("devices.json")
        except FileNotFoundError:
            approved_devices = []

        approved_devices.append(
            {
                "label": label,
                "owner": owner,
                "name": device_to_pair["name"],
                "mac": device_to_pair["mac"],
            }
        )

        with open("devices.json", "w") as f:
            json.dump(approved_devices, f)

    except (IndexError, ValueError):
        print("Invalid selection.")


if __name__ == "__main__":
    main()
