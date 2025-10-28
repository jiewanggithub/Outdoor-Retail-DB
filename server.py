"""
Columbia's COMS W4111.001 Introduction to Databases
Flask webserver (raw SQL, no ORM) integrated with your Outdoor Retail DB.
Run locally:
    python server.py --debug
Go to http://localhost:8111
"""
import os
from sqlalchemy import create_engine, text
from sqlalchemy.pool import NullPool
from flask import Flask, request, render_template, g, redirect, Response, abort, flash, url_for

# ------------------------------------------------------------------------------
# App + DB setup (keeps your professor's pattern)
# ------------------------------------------------------------------------------
tmpl_dir = os.path.join(os.path.dirname(os.path.abspath(__file__)), 'templates')
app = Flask(__name__, template_folder=tmpl_dir)
app.secret_key = os.getenv("SECRET_KEY", "dev-secret")  # for flash messages

# >>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>  EDIT ME  <<<<<<<<<<<<<<<<<<<<<<<<<<<<<<<<<
DATABASE_USERNAME = "lp3159"          
DATABASE_PASSWRD = "935487"           
DATABASE_HOST = "34.139.8.30"
DATABASEURI = f"postgresql://{DATABASE_USERNAME}:{DATABASE_PASSWRD}@{DATABASE_HOST}/proj1part2"
# >>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>  EDIT ME  <<<<<<<<<<<<<<<<<<<<<<<<<<<<<<<<<

engine = create_engine(DATABASEURI, poolclass=NullPool, pool_pre_ping=True)

# ------------------------------------------------------------------------------
# Connection lifecycle
# ------------------------------------------------------------------------------
@app.before_request
def before_request():
    try:
        g.conn = engine.connect()
    except Exception:
        print("uh oh, problem connecting to database")
        import traceback; traceback.print_exc()
        g.conn = None

@app.teardown_request
def teardown_request(exception):
    try:
        if g.get("conn"):
            g.conn.close()
    except Exception:
        pass

# ------------------------------------------------------------------------------
# Home
# ------------------------------------------------------------------------------
@app.route('/')
def index():
    # You can add any light health check here if needed
    return render_template("index.html", title="Outdoor Retail DB")

# ------------------------------------------------------------------------------
# Customers (list)  /customers
# ------------------------------------------------------------------------------
@app.route('/customers')
def customers():
    sql = """
        SELECT c.customer_id, c.first_name, c.last_name, c.email_addr,
               a.account_id, a.account_balance
        FROM customers c
        LEFT JOIN accounts a ON a.customer_id = c.customer_id
        ORDER BY c.customer_id
    """
    cur = g.conn.execute(text(sql))
    cols = list(cur.keys())
    rows = cur.fetchall()
    cur.close()
    return render_template("customers.html", cols=cols, rows=rows, title="Customers")

# ------------------------------------------------------------------------------
# New customer + account  /customers/new
# ------------------------------------------------------------------------------
@app.route('/customers/new', methods=['GET', 'POST'])
def new_customer():
    if request.method == 'POST':
        fn  = request.form['first_name']
        ln  = request.form['last_name']
        dob = request.form['dob']                 # YYYY-MM-DD
        em  = request.form['email_addr']
        ph  = request.form['phone_number']
        bal = float(request.form.get('account_balance', 0) or 0)

        # Insert customer, then account
        cur = g.conn.execute(text("""
            INSERT INTO customers (first_name, last_name, dob, email_addr, phone_number)
            VALUES (:fn, :ln, :dob, :em, :ph)
            RETURNING customer_id
        """), dict(fn=fn, ln=ln, dob=dob, em=em, ph=ph))
        cid = cur.scalar()

        g.conn.execute(text("""
            INSERT INTO accounts (customer_id, account_balance)
            VALUES (:cid, :bal)
        """), dict(cid=cid, bal=bal))

        g.conn.commit()
        flash("Customer and account created.", "success")
        return redirect(url_for('customers'))

    return render_template('new_customer.html', title='New Customer')

# ------------------------------------------------------------------------------
# Stores (list)  /stores
# ------------------------------------------------------------------------------
@app.route('/stores')
def stores():
    sql = "SELECT store_id, store_name, store_addr, store_zipcode FROM stores ORDER BY store_id"
    cur = g.conn.execute(text(sql))
    cols = list(cur.keys())
    rows = cur.fetchall()
    cur.close()
    return render_template("stores.html", cols=cols, rows=rows, title="Stores")

# ------------------------------------------------------------------------------
# Items (list)  /items
# ------------------------------------------------------------------------------
@app.route('/items')
def items():
    sql = "SELECT item_id, model_name, type, price, is_rentable FROM items ORDER BY item_id"
    cur = g.conn.execute(text(sql))
    cols = list(cur.keys())
    rows = cur.fetchall()
    cur.close()
    return render_template("items.html", cols=cols, rows=rows, title="Items")

# ------------------------------------------------------------------------------
# Inventory (join)  /stock
# ------------------------------------------------------------------------------
@app.route('/stock')
def stock():
    sql = """
        SELECT s.store_name, i.model_name, st.quantity
        FROM store_item_stock st
        JOIN stores s ON s.store_id = st.store_id
        JOIN items  i ON i.item_id  = st.item_id
        ORDER BY s.store_name, i.model_name
    """
    cur = g.conn.execute(text(sql))
    cols = list(cur.keys())
    rows = cur.fetchall()
    cur.close()
    return render_template("generic_table.html", title="Store Inventory", cols=cols, rows=rows)

# ------------------------------------------------------------------------------
# Orders (list)  /orders
# ------------------------------------------------------------------------------
@app.route('/orders')
def orders():
    sql = """
        SELECT o.order_id, o.checkout_ts, o.order_total,
               c.first_name || ' ' || c.last_name AS customer,
               s.store_name
        FROM orders o
        JOIN customers c ON c.customer_id = o.customer_id
        JOIN stores    s ON s.store_id    = o.store_id
        ORDER BY o.checkout_ts DESC, o.order_id DESC
    """
    cur = g.conn.execute(text(sql))
    cols = list(cur.keys())
    rows = cur.fetchall()
    cur.close()
    return render_template("generic_table.html", title="Orders", cols=cols, rows=rows)

# ------------------------------------------------------------------------------
# New order (one line item)  /orders/new
# ------------------------------------------------------------------------------
@app.route('/orders/new', methods=['GET', 'POST'])
def new_order():
    if request.method == 'POST':
        customer_id = int(request.form['customer_id'])
        account_id  = int(request.form['account_id'])
        store_id    = int(request.form['store_id'])
        item_id     = int(request.form['item_id'])
        quantity    = int(request.form['quantity'])
        unit_price  = float(request.form['unit_price'])

        # Create order + line item + optional inventory decrement
        cur = g.conn.execute(text("""
            INSERT INTO orders (customer_id, account_id, store_id, checkout_ts, order_total)
            VALUES (:cid, :aid, :sid, NOW(), :total)
            RETURNING order_id
        """), dict(cid=customer_id, aid=account_id, sid=store_id, total=quantity*unit_price))
        order_id = cur.scalar()

        g.conn.execute(text("""
            INSERT INTO order_items (order_id, item_id, quantity, unit_price)
            VALUES (:oid, :iid, :qty, :price)
        """), dict(oid=order_id, iid=item_id, qty=quantity, price=unit_price))

        # Decrement inventory (optional; remove if you don't want this)
        g.conn.execute(text("""
            UPDATE store_item_stock
               SET quantity = quantity - :qty
             WHERE store_id = :sid AND item_id = :iid
        """), dict(qty=quantity, sid=store_id, iid=item_id))

        g.conn.commit()
        flash(f"Order {order_id} created.", "success")
        return redirect(url_for('orders'))

    # Populate dropdowns
    cur = g.conn.execute(text("SELECT customer_id, first_name || ' ' || last_name AS name FROM customers ORDER BY customer_id"))
    customers = cur.fetchall(); cur.close()

    cur = g.conn.execute(text("SELECT account_id, customer_id FROM accounts ORDER BY account_id"))
    accounts = cur.fetchall(); cur.close()

    cur = g.conn.execute(text("SELECT store_id, store_name FROM stores ORDER BY store_id"))
    stores = cur.fetchall(); cur.close()

    cur = g.conn.execute(text("SELECT item_id, model_name, price FROM items ORDER BY item_id"))
    items = cur.fetchall(); cur.close()

    return render_template("new_order.html",
                           customers=customers, accounts=accounts, stores=stores, items=items,
                           title="New Order")

# ------------------------------------------------------------------------------
# Item lookup & filtering  /items/search?name=&type=&min_price=&max_price=
# ------------------------------------------------------------------------------
@app.route("/items/search")
def items_search():
    name = request.args.get("name", "").strip()
    itype = request.args.get("type", "").strip()
    min_price = request.args.get("min_price", type=float)
    max_price = request.args.get("max_price", type=float)

    clauses, params = [], {}
    if name:
        clauses.append("LOWER(i.model_name) LIKE LOWER(:name)")
        params["name"] = f"%{name}%"
    if itype:
        clauses.append("LOWER(i.type) = LOWER(:type)")
        params["type"] = itype
    if min_price is not None:
        clauses.append("i.price >= :min_price")
        params["min_price"] = min_price
    if max_price is not None:
        clauses.append("i.price <= :max_price")
        params["max_price"] = max_price

    where_sql = ("WHERE " + " AND ".join(clauses)) if clauses else ""
    sql = f"""
        SELECT i.item_id, i.model_name, i.type, i.price, i.is_rentable
        FROM items i
        {where_sql}
        ORDER BY i.model_name
        LIMIT 200
    """
    cur = g.conn.execute(text(sql), params)
    cols = list(cur.keys())
    rows = cur.fetchall()
    cur.close()
    return render_template(
        "items_search.html",
        cols=cols, rows=rows,
        q=dict(name=name, type=itype, min_price=min_price, max_price=max_price),
        title="Search Items"
    )

# ------------------------------------------------------------------------------
# Customer private account page  /account/<customer_id>
# ------------------------------------------------------------------------------
@app.route("/account/<int:customer_id>")
def account(customer_id):
    prof_sql = """
      SELECT c.customer_id, c.first_name, c.last_name, c.dob, c.email_addr, c.phone_number,
             a.account_id, a.account_balance
      FROM customers c
      LEFT JOIN accounts a ON a.customer_id = c.customer_id
      WHERE c.customer_id = :cid
    """
    cur = g.conn.execute(text(prof_sql), {"cid": customer_id})
    p_cols = list(cur.keys())
    p_rows = cur.fetchall()
    cur.close()
    if not p_rows:
        flash("Customer not found.", "danger")
        return redirect(url_for("customers"))

    orders_sql = """
      SELECT o.order_id, o.checkout_ts, o.order_total,
             i.model_name, oi.quantity, oi.unit_price, oi.line_total
      FROM orders o
      JOIN order_items oi ON oi.order_id = o.order_id
      JOIN items i        ON i.item_id   = oi.item_id
      WHERE o.customer_id = :cid
      ORDER BY o.checkout_ts DESC, o.order_id DESC
    """
    cur = g.conn.execute(text(orders_sql), {"cid": customer_id})
    o_cols = list(cur.keys())
    o_rows = cur.fetchall()
    cur.close()

    return render_template("account.html",
                           p_cols=p_cols, p_rows=p_rows,
                           o_cols=o_cols, o_rows=o_rows,
                           title=f"Account {customer_id}")

# ------------------------------------------------------------------------------
# Welcome page (brands + staff)  /welcome
# ------------------------------------------------------------------------------
@app.route("/welcome")
def welcome():
    cur = g.conn.execute(text("SELECT brand_name FROM suppliers ORDER BY brand_name LIMIT 50"))
    brands = cur.fetchall(); cur.close()

    s_sql = """
      SELECT e.first_name || ' ' || e.last_name AS name, e.store_id, st.position
      FROM staff st
      JOIN employees e ON e.employee_id = st.employee_id
      ORDER BY e.store_id, name
    """
    cur = g.conn.execute(text(s_sql))
    staff = cur.fetchall(); cur.close()

    return render_template("welcome.html", brands=brands, staff=staff, title="Welcome")

# ------------------------------------------------------------------------------
# Simple report: top selling items (units sold)  /reports/top-items
# ------------------------------------------------------------------------------
@app.route("/reports/top-items")
def report_top_items():
    sql = """
        SELECT i.model_name, SUM(oi.quantity) AS units_sold
        FROM order_items oi
        JOIN items i ON i.item_id = oi.item_id
        GROUP BY i.model_name
        ORDER BY units_sold DESC
        LIMIT 10
    """
    cur = g.conn.execute(text(sql))
    cols = list(cur.keys())
    rows = cur.fetchall()
    cur.close()
    return render_template("generic_table.html", title="Top Selling Items", cols=cols, rows=rows)

# ------------------------------------------------------------------------------
# CLI runner (keeps professor's signature; default port 8111)
# ------------------------------------------------------------------------------

if __name__ == "__main__":
    import click

    @click.command()
    @click.option('--debug', is_flag=True)
    @click.option('--threaded', is_flag=True)
    @click.argument('HOST', default='0.0.0.0')
    @click.argument('PORT', default=8111, type=int)
    def run(debug, threaded, host, port):
        print(f"running on {host}:{port}")
        app.run(host=host, port=port, debug=debug, threaded=threaded)

    run()
