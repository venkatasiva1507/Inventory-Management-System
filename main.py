from database import get_connection
from decimal import Decimal, InvalidOperation
from mysql.connector import Error


def read_number(message, allow_zero=False):
    try:
        value = Decimal(input(message))
        if not value.is_finite():
            raise ValueError
        if value < 0 or (not allow_zero and value == 0):
            print("Enter a valid positive number.")
            return None
        return value
    except (InvalidOperation, ValueError):
        print("Enter a valid number.")
        return None


def view_inventory():
    con = get_connection()
    if not con:
        return

    cur = con.cursor()
    cur.execute("""
        SELECT product_id, name, category, quantity,
               cost_price, selling_price
        FROM products ORDER BY product_id
    """)
    rows = cur.fetchall()

    print("\nID | ITEM | CATEGORY | STOCK | COST | SELLING")
    if not rows:
        print("No products in inventory.")

    for row in rows:
        print(*row, sep=" | ")

    cur.close()
    con.close()


def add_item():
    name = input("Enter item name: ").strip()
    category = input("Enter category: ").strip()

    if not name or not category:
        print("Name and category cannot be empty.")
        return

    qty = read_number("Enter quantity: ", allow_zero=True)
    if qty is None:
        return
    cost = read_number("Enter cost price: ")
    if cost is None:
        return
    selling = read_number("Enter selling price: ")
    if selling is None:
        return

    if selling < cost:
        print("Warning: selling price is below cost price.")

    con = get_connection()
    if not con:
        return

    cur = con.cursor()
    try:
        cur.execute("""
            INSERT INTO products
            (name, category, quantity, cost_price, selling_price)
            VALUES (%s, %s, %s, %s, %s)
        """, (name, category, qty, cost, selling))
        con.commit()
        print("Product added successfully.")
    except Error as e:
        con.rollback()
        print("Unable to add product:", e)
    finally:
        cur.close()
        con.close()


def remove_item():
    view_inventory()
    product_id = input("Enter product ID to remove: ").strip()

    con = get_connection()
    if not con:
        return
    cur = con.cursor()

    try:
        cur.execute(
            "DELETE FROM products WHERE product_id = %s",
            (product_id,)
        )
        if cur.rowcount:
            con.commit()
            print("Product removed successfully.")
        else:
            con.rollback()
            print("Product ID not found.")
    except Error:
        con.rollback()
        print("This product may be part of an existing bill.")
        print("Keep it in the database to preserve sales history.")
    finally:
        cur.close()
        con.close()


def update_item():
    view_inventory()
    product_id = input("Enter product ID to update: ").strip()

    con = get_connection()
    if not con:
        return
    cur = con.cursor()

    try:
        cur.execute(
            "SELECT name, category, quantity, cost_price, selling_price "
            "FROM products WHERE product_id = %s",
            (product_id,)
        )
        product = cur.fetchone()

        if not product:
            print("Product not found.")
            return

        name, category, qty, cost, selling = product

        print("Leave a field empty to keep its current value.")
        new_name = input(f"Name [{name}]: ").strip() or name
        new_category = input(
            f"Category [{category}]: "
        ).strip() or category

        raw_qty = input(f"Quantity [{qty}]: ").strip()
        raw_cost = input(f"Cost price [{cost}]: ").strip()
        raw_selling = input(f"Selling price [{selling}]: ").strip()

        new_qty = qty
        new_cost = cost
        new_selling = selling

        try:
            if raw_qty:
                new_qty = Decimal(raw_qty)
            if raw_cost:
                new_cost = Decimal(raw_cost)
            if raw_selling:
                new_selling = Decimal(raw_selling)

            if (not new_qty.is_finite() or
                    not new_cost.is_finite() or
                    not new_selling.is_finite() or
                    new_qty < 0 or new_cost <= 0 or new_selling <= 0):
                raise ValueError
        except (InvalidOperation, ValueError):
            print("Invalid quantity or price. No changes saved.")
            return

        cur.execute("""
            UPDATE products
            SET name=%s, category=%s, quantity=%s,
                cost_price=%s, selling_price=%s
            WHERE product_id=%s
        """, (
            new_name, new_category, new_qty,
            new_cost, new_selling, product_id
        ))
        con.commit()
        print("Product updated successfully.")

    except Error as e:
        con.rollback()
        print("Update failed:", e)
    finally:
        cur.close()
        con.close()


def view_customers():
    con = get_connection()
    if not con:
        return
    cur = con.cursor()

    cur.execute("""
        SELECT c.customer_id, c.name,
               COALESCE(SUM(o.total_amount), 0) AS total_spent
        FROM customers c
        LEFT JOIN orders o ON c.customer_id = o.customer_id
        GROUP BY c.customer_id, c.name
        ORDER BY c.customer_id
    """)

    print("\nCUSTOMER ID | NAME | TOTAL SPENT")
    for row in cur.fetchall():
        print(*row, sep=" | ")

    cur.close()
    con.close()


def view_report():
    view_inventory()


def total_revenue():
    con = get_connection()
    if not con:
        return
    cur = con.cursor()

    cur.execute("SELECT COALESCE(SUM(total_amount), 0) FROM orders")
    revenue = cur.fetchone()[0]
    print("Total revenue:", revenue)

    cur.close()
    con.close()


def owner_menu():
    while True:
        print("""
----- OWNER SECTION -----
1. Add item
2. Remove item
3. Update item
4. View inventory
5. View customers
6. View report
7. Total revenue
8. Exit section
""")
        choice = input("Enter your choice: ")

        if choice == "1":
            add_item()
        elif choice == "2":
            remove_item()
        elif choice == "3":
            update_item()
        elif choice == "4":
            view_inventory()
        elif choice == "5":
            view_customers()
        elif choice == "6":
            view_report()
        elif choice == "7":
            total_revenue()
        elif choice == "8":
            break
        else:
            print("Incorrect choice.")


def show_available_products():
    con = get_connection()
    if not con:
        return
    cur = con.cursor()

    cur.execute("""
        SELECT product_id, name, category, quantity, selling_price
        FROM products WHERE quantity > 0 ORDER BY name
    """)

    print("\nID | ITEM | CATEGORY | STOCK | SELLING PRICE")
    rows = cur.fetchall()
    if not rows:
        print("No products currently available.")
    for row in rows:
        print(*row, sep=" | ")

    cur.close()
    con.close()


def checkout(customer_id, cart):
    if not cart:
        print("Cart is empty.")
        return

    con = get_connection()
    if not con:
        return

    cur = con.cursor()

    try:
        # Lock product rows while checking and deducting stock.
        product_ids = sorted(cart)
        placeholders = ",".join(["%s"] * len(product_ids))
        cur.execute(
            "SELECT product_id, name, quantity, selling_price "
            f"FROM products WHERE product_id IN ({placeholders}) "
            "ORDER BY product_id FOR UPDATE",
            tuple(product_ids)
        )
        products = {row[0]: row for row in cur.fetchall()}

        total = Decimal("0.00")
        bill_items = []

        for product_id, qty in cart.items():
            product = products.get(product_id)
            if product is None:
                raise ValueError(f"Product ID {product_id} no longer exists.")

            _, name, stock, selling_price = product
            if qty <= 0 or qty > stock:
                raise ValueError(f"Insufficient stock for {name}.")

            line_total = qty * selling_price
            total += line_total
            bill_items.append(
                (product_id, name, qty, selling_price, line_total)
            )

        cur.execute(
            "INSERT INTO orders (customer_id, total_amount) VALUES (%s, %s)",
            (customer_id, total)
        )
        order_id = cur.lastrowid

        for product_id, name, qty, selling, line_total in bill_items:
            cur.execute("""
                UPDATE products
                SET quantity = quantity - %s
                WHERE product_id = %s AND quantity >= %s
            """, (qty, product_id, qty))

            if cur.rowcount != 1:
                raise ValueError(f"Stock changed for {name}. Please retry.")

            cur.execute("""
                INSERT INTO order_items
                (order_id, product_id, product_name, quantity,
                 selling_price, line_total)
                VALUES (%s, %s, %s, %s, %s, %s)
            """, (
                order_id, product_id, name, qty, selling, line_total
            ))

        con.commit()

        print("\n--------- BILL ---------")
        print("Bill number:", order_id)
        for _, name, qty, selling, line_total in bill_items:
            print(f"{name} | Qty: {qty} | Price: {selling} "
                  f"| Total: {line_total}")
        print("------------------------")
        print("TOTAL BILL:", total)
        print("Billing completed successfully.")
        return True

    except (Error, ValueError) as e:
        con.rollback()
        print("Checkout failed:", e)
        print("No sale was saved. Please check stock and try again.")
        return False 
    finally:
        cur.close()
        con.close()


def user_menu():
    name = input("Enter your name: ").strip()
    if not name:
        print("Name cannot be empty.")
        return

    con = get_connection()
    if not con:
        return
    cur = con.cursor()

    try:
        cur.execute(
            "INSERT INTO customers (name) VALUES (%s) "
            "ON DUPLICATE KEY UPDATE customer_id=LAST_INSERT_ID(customer_id)",
            (name,)
        )
        customer_id = cur.lastrowid
        con.commit()
    except Error as e:
        con.rollback()
        print("Could not register customer:", e)
        cur.close()
        con.close()
        return

    cur.close()
    con.close()

    cart = {}

    while True:
        print("""
----- USER SECTION -----
1. View available items
2. Add item to cart
3. Remove item from cart
4. Modify cart quantity
5. View cart
6. Total bill / Checkout
7. Exit
""")
        choice = input("Enter your choice: ")

        if choice == "1":
            show_available_products()

        elif choice == "2":
            show_available_products()
            try:
                product_id = int(input("Enter product ID: "))
            except ValueError:
                print("Enter a valid product ID.")
                continue

            qty = read_number("Enter quantity: ")
            if qty is None:
                continue

            con = get_connection()
            if not con:
                continue
            cur = con.cursor()
            cur.execute(
                "SELECT name, quantity FROM products WHERE product_id=%s",
                (product_id,)
            )
            product = cur.fetchone()
            cur.close()
            con.close()

            if not product:
                print("Product not found.")
                continue

            name, stock = product
            requested = cart.get(product_id, Decimal("0")) + qty

            if requested > stock:
                print("Insufficient stock.")
            else:
                cart[product_id] = requested
                print(name, "added to cart.")

        elif choice == "3":
            try:
                product_id = int(input("Enter product ID to remove: "))
            except ValueError:
                print("Enter a valid product ID.")
                continue

            if product_id in cart:
                del cart[product_id]
                print("Item removed from cart.")
            else:
                print("Item not found in cart.")

        elif choice == "4":
            try:
                product_id = int(input("Enter product ID to modify: "))
            except ValueError:
                print("Enter a valid product ID.")
                continue

            if product_id not in cart:
                print("Item not found in cart.")
                continue

            qty = read_number("Enter new quantity: ")
            if qty is None:
                continue

            con = get_connection()
            if not con:
                continue
            cur = con.cursor()
            cur.execute(
                "SELECT quantity FROM products WHERE product_id=%s",
                (product_id,)
            )
            row = cur.fetchone()
            cur.close()
            con.close()

            if row and qty <= row[0]:
                cart[product_id] = qty
                print("Cart updated.")
            else:
                print("Insufficient stock or product unavailable.")

        elif choice == "5":
            print("\nID | ITEM | QUANTITY | PRICE | TOTAL")
            if not cart:
                print("Cart is empty.")
                continue

            con = get_connection()
            if not con:
                continue
            cur = con.cursor()

            total = Decimal("0")
            for product_id, qty in cart.items():
                cur.execute(
                    "SELECT name, selling_price FROM products "
                    "WHERE product_id=%s",
                    (product_id,)
                )
                row = cur.fetchone()
                if row:
                    name, price = row
                    line_total = qty * price
                    total += line_total
                    print(product_id, name, qty, price, line_total, sep=" | ")

            print("Cart total:", total)
            cur.close()
            con.close()

        elif choice == "6":
            if checkout(customer_id, cart):
                cart.clear()

        elif choice == "7":
            break

        else:
            print("Incorrect choice.")


def main():
    print("*" * 10, "WELCOME TO ALL IN ONE SHOP", "*" * 10)

    while True:
        print("""
----- SELECT YOUR ROLE -----
1. OWNER
2. USER
3. EXIT
""")
        choice = input("Enter your role (1/2/3): ")

        if choice == "1":
            owner_menu()
        elif choice == "2":
            user_menu()
        elif choice == "3":
            print("SHOP IS CLOSED")
            print("THANK YOU, VISIT AGAIN")
            break
        else:
            print("Incorrect role choice.")


if __name__ == "__main__":
    main()



    




      
        

