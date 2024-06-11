import utils
import db


def create_pin(creator_email, pin, label):
    user_id = db.get_user(creator_email).id
    salt = utils.generate_salt()
    hashed_pin = utils.hash_secret(salt=salt, payload=pin)

    pin = db.save_pin(user_id, hashed_pin, salt, label)

    print("New PIN for stored.")


def list_pins(apartment_number):
    """List all PINs."""
    apartment = db.get_apartment_by_number(apartment_number)

    if not apartment:
        print("Apartment not found.")
        return []

    pins = db.get_pins_by_apartment(apartment.id)

    print("PINs:")
    for i, pin in enumerate(pins, start=1):
        print(
            f"{i}. User ID {pin['user_id']}, created at {pin['created_at']}"
        )  # todo: fetch user email

    return pins


def main():
    while True:
        print("\n1. Create PIN\n2. Delete PIN\n3. List PINs\n4. Exit")
        choice = input("Enter your choice: ")
        if choice == "1":
            creator_email = input("Enter the user's email address: ")
            pin = input("Enter PIN: ")
            label = input("Enter a label for this PIN: ")
            create_pin(creator_email, pin, label)
        elif choice == "2":
            apartment_number = input("Enter apartment number: ")

            pins = list_pins(apartment_number)

            choice = int(input("Enter the number of the PIN to delete: ")) - 1
            if 0 <= choice < len(pins):
                try:
                    pin_id = pins[choice]["id"]
                    db.remove_pin(pin_id)
                    print("PIN deleted.")
                except Exception as e:
                    print(f"An error occurred: {e}")
            else:
                print("Invalid choice, please try again.")
        elif choice == "3":
            print("\n")
            apartment_number = input("Enter apartment number: ")
            list_pins(apartment_number)
        elif choice == "4":
            print("Exiting...")
            break
        else:
            print("Invalid choice, please try again.")


if __name__ == "__main__":
    main()
