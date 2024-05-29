import utils
import json
import datetime


def load_data():
    try:
        with open("data.json", "r") as file:
            return json.load(file)
    except FileNotFoundError:
        return {"apartments": {}}


def save_data(data):
    with open("data.json", "w") as file:
        json.dump(data, file, indent=4)


def create_pin(apartment_number, pin, creator_email, label):
    data = load_data()
    hashed_pin = utils.hash_secret(salt=apartment_number, payload=pin)
    entry = {
        "label": label,
        "hashed_pin": hashed_pin,
        "creator_email": creator_email,
        "created_at": datetime.datetime.now().isoformat(),
    }
    data["apartments"].setdefault(
        apartment_number, {"users": [], "pins": [], "devices": []}
    )
    data["apartments"][apartment_number].setdefault("pins", [])
    data["apartments"][apartment_number]["pins"].append(entry)
    save_data(data)
    print(f"New PIN for apartment number {apartment_number} stored.")


def delete_pin(apartment_number, hashed_pin):
    """Delete an existing PIN entry."""
    data = load_data()

    if apartment_number not in data["apartments"]:
        print("Apartment number not found.")
        return False
    if "pins" not in data["apartments"][apartment_number]:
        print("No PINs stored for this apartment.")
        return False
    new_pins = [
        pin
        for pin in data["apartments"][apartment_number]["pins"]
        if pin["hashed_pin"] != hashed_pin
    ]
    data["apartments"][apartment_number]["pins"] = new_pins
    save_data(data)
    print("PIN not found.")
    return False


def list_pins():
    """List all PINs."""
    data = load_data()
    for apartment_number, apartment in data["apartments"].items():
        print(f"Apartment Number: {apartment_number}")
        if "pins" not in apartment or not apartment["pins"]:
            print("  No PINs stored for this apartment.")
            continue
        for pin in apartment.get("pins", []):
            print(
                f"  Hashed PIN: {pin['hashed_pin']}, Creator: {pin['creator_email']}, Label: {pin['label']}, Created At: {pin['created_at']}"
            )


def main():
    data = load_data()
    while True:
        print("\n1. Create PIN\n2. Delete PIN\n3. List PINs\n4. Exit")
        choice = input("Enter your choice: ")
        if choice == "1":
            apartment_number = input("Enter apartment number (two digits): ")
            pin = input("Enter PIN: ")
            creator_email = input("Enter your email address: ")
            label = input("Enter a label for this PIN: ")
            create_pin(apartment_number, pin, creator_email, label)
        elif choice == "2":
            apartment_number = input("Enter apartment number (two digits): ")
            pins = data["apartments"][apartment_number].get("pins", [])
            if not pins:
                print("No PINs stored for this apartment.")
                continue
            print("Select a PIN to delete:")
            for index, pin in enumerate(pins):
                print(
                    f"{index + 1}. Created by {pin['creator_email']} on {pin['created_at']}"
                )
            choice = int(input("Enter the number of the PIN to delete: ")) - 1
            if 0 <= choice < len(pins):
                if delete_pin(apartment_number, pins[choice]["hashed_pin"]):
                    print("PIN deleted.")
        elif choice == "3":
            print("\n")
            list_pins()
        elif choice == "4":
            print("Exiting...")
            break
        else:
            print("Invalid choice, please try again.")


if __name__ == "__main__":
    main()
