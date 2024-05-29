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


def delete_pin(pins):
    """Delete an existing PIN entry."""
    apartment_number = input("Enter apartment number to delete PIN from (two digits): ")
    if apartment_number in pins:
        print("Select a PIN to delete:")
        for index, pin in enumerate(pins[apartment_number]):
            print(f"{index + 1}. Created by {pin['creator']} on {pin['created_at']}")
        choice = int(input("Enter the number of the PIN to delete: ")) - 1
        if 0 <= choice < len(pins[apartment_number]):
            del pins[apartment_number][choice]
            print("PIN deleted.")
            if not pins[apartment_number]:  # Remove the entry if no pins left
                del pins[apartment_number]
        else:
            print("Invalid PIN selection.")
    else:
        print("Apartment number not found.")


def list_pins(pins):
    """List all PINs."""
    for apartment_number, entries in pins.items():
        print(f"Apartment Number: {apartment_number}")
        for pin in entries:
            print(
                f"    Hashed PIN: {pin['hashed_pin']}, Creator: {pin['creator']}, Created At: {pin['created_at']}"
            )


def main():
    data = load_data()
    while True:
        print("\n1. Create PIN\n2. Delete PIN\n3. List PINs\n4. Exit")
        choice = input("Enter your choice: ")
        if choice == "1":
            create_pin(data)
        elif choice == "2":
            delete_pin(data)
        elif choice == "3":
            list_pins(data)
        elif choice == "4":
            save_data(data)
            print("Exiting...")
            break
        else:
            print("Invalid choice, please try again.")
        save_data(data)  # Save after every operation


if __name__ == "__main__":
    main()
