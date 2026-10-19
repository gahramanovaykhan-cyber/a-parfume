from flask import Flask, render_template, request, redirect, url_for, flash, session, Response
import sqlite3, os, csv, io
from datetime import datetime
from functools import wraps

APP_DIR = os.path.dirname(os.path.abspath(__file__))
DB_PATH = os.path.join(APP_DIR, "a_parfume.db")
app = Flask(__name__)
app.secret_key = "change-this-secret-key"

def db():
    con = sqlite3.connect(DB_PATH)
    con.row_factory = sqlite3.Row
    return con

def init_db():
    with db() as con:
        con.execute("""CREATE TABLE IF NOT EXISTS products(
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            name TEXT NOT NULL,
            brand TEXT DEFAULT '',
            kind TEXT NOT NULL DEFAULT 'Doldurma',
            size_ml REAL NOT NULL DEFAULT 5,
            cost REAL NOT NULL DEFAULT 0,
            price REAL NOT NULL DEFAULT 0,
            stock REAL NOT NULL DEFAULT 0,
            created_at TEXT NOT NULL
        )""")
        con.execute("""CREATE TABLE IF NOT EXISTS orders(
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            product_id INTEGER NOT NULL,
            customer TEXT DEFAULT '',
            quantity REAL NOT NULL,
            unit_price REAL NOT NULL,
            total REAL NOT NULL,
            created_at TEXT NOT NULL,
            FOREIGN KEY(product_id) REFERENCES products(id)
        )""")

def money(n):
    return f"{float(n or 0):.2f}"

@app.template_filter("money")
def money_filter(n):
    return money(n)

@app.route("/")
def index():
    with db() as con:
        products = con.execute("SELECT * FROM products ORDER BY id DESC").fetchall()
        stats = con.execute("""SELECT
            (SELECT COUNT(*) FROM products) AS product_count,
            (SELECT COALESCE(SUM(stock),0) FROM products) AS stock_count,
            (SELECT COALESCE(SUM(total),0) FROM orders) AS sales_total,
            (SELECT COUNT(*) FROM orders) AS order_count""").fetchone()
        recent = con.execute("""SELECT orders.*, products.name AS product_name
            FROM orders JOIN products ON products.id=orders.product_id
            ORDER BY orders.id DESC LIMIT 5""").fetchall()
    return render_template("dashboard.html", stats=stats, recent=recent)

@app.route("/products", methods=["GET","POST"])
def products():
    if request.method == "POST":
        name = request.form.get("name","").strip()
        brand = request.form.get("brand","").strip()
        kind = request.form.get("kind","Doldurma")
        try:
            size_ml = float(request.form.get("size_ml","5"))
            cost = float(request.form.get("cost","0"))
            price = float(request.form.get("price","0"))
            stock = float(request.form.get("stock","0"))
        except ValueError:
            flash("Həcm, qiymət və stok sahələrinə düzgün rəqəm yaz.", "error")
            return redirect(url_for("products"))
        if not name or size_ml <= 0 or cost < 0 or price < 0 or stock < 0:
            flash("Məhsul adı yaz və rəqəmləri düzgün daxil et.", "error")
            return redirect(url_for("products"))
        with db() as con:
            con.execute("""INSERT INTO products(name,brand,kind,size_ml,cost,price,stock,created_at)
                VALUES(?,?,?,?,?,?,?,?)""",
                (name,brand,kind,size_ml,cost,price,stock,datetime.now().strftime("%Y-%m-%d %H:%M")))
        flash("Məhsul əlavə edildi.", "success")
        return redirect(url_for("products"))
    q = request.args.get("q","").strip()
    with db() as con:
        if q:
            items = con.execute("SELECT * FROM products WHERE name LIKE ? OR brand LIKE ? ORDER BY id DESC",
                                (f"%{q}%",f"%{q}%")).fetchall()
        else:
            items = con.execute("SELECT * FROM products ORDER BY id DESC").fetchall()
    return render_template("products.html", products=items, q=q)

@app.post("/products/<int:product_id>/delete")
def delete_product(product_id):
    with db() as con:
        used = con.execute("SELECT COUNT(*) FROM orders WHERE product_id=?", (product_id,)).fetchone()[0]
        if used:
            flash("Bu məhsul sifarişdə istifadə olunub, silmək əvəzinə stokunu 0 et.", "error")
        else:
            con.execute("DELETE FROM products WHERE id=?", (product_id,))
            flash("Məhsul silindi.", "success")
    return redirect(url_for("products"))

@app.route("/orders", methods=["GET","POST"])
def orders():
    if request.method == "POST":
        try:
            product_id = int(request.form.get("product_id","0"))
            quantity = float(request.form.get("quantity","1"))
        except ValueError:
            flash("Məhsul və miqdar düzgün seçilməyib.", "error")
            return redirect(url_for("orders"))
        customer = request.form.get("customer","").strip()
        with db() as con:
            product = con.execute("SELECT * FROM products WHERE id=?", (product_id,)).fetchone()
            if not product:
                flash("Əvvəlcə məhsul əlavə et.", "error")
            elif quantity <= 0:
                flash("Miqdar 0-dan böyük olmalıdır.", "error")
            elif quantity > product["stock"]:
                flash(f"Stokda kifayət qədər məhsul yoxdur. Qalıq: {product['stock']:g}", "error")
            else:
                total = quantity * product["price"]
                now = datetime.now().strftime("%Y-%m-%d %H:%M")
                con.execute("INSERT INTO orders(product_id,customer,quantity,unit_price,total,created_at) VALUES(?,?,?,?,?,?)",
                            (product_id,customer,quantity,product["price"],total,now))
                con.execute("UPDATE products SET stock=stock-? WHERE id=?", (quantity,product_id))
                flash(f"Sifariş qeydə alındı. Məbləğ: {total:.2f} AZN", "success")
        return redirect(url_for("orders"))
    with db() as con:
        products = con.execute("SELECT * FROM products WHERE stock > 0 ORDER BY name").fetchall()
        orders_list = con.execute("""SELECT orders.*, products.name AS product_name, products.size_ml, products.kind
            FROM orders JOIN products ON products.id=orders.product_id ORDER BY orders.id DESC LIMIT 100""").fetchall()
    return render_template("orders.html", products=products, orders=orders_list)

@app.route("/reports")
def reports():
    with db() as con:
        total = con.execute("SELECT COALESCE(SUM(total),0) FROM orders").fetchone()[0]
        cost = con.execute("SELECT COALESCE(SUM(quantity * (SELECT cost FROM products WHERE products.id=orders.product_id)),0) FROM orders").fetchone()[0]
        rows = con.execute("""SELECT products.name, products.brand, products.kind, products.size_ml,
            SUM(orders.quantity) AS sold_qty, SUM(orders.total) AS sales
            FROM orders JOIN products ON products.id=orders.product_id
            GROUP BY products.id ORDER BY sales DESC""").fetchall()
    return render_template("reports.html", total=total, profit=total-cost, rows=rows)

@app.route("/export.csv")
def export_csv():
    output = io.StringIO()
    writer = csv.writer(output)
    writer.writerow(["ID","Ətir","Brend","Növ","Həcm (ml)","Alış qiyməti","Satış qiyməti","Stok"])
    with db() as con:
        for p in con.execute("SELECT * FROM products ORDER BY id"):
            writer.writerow([p["id"],p["name"],p["brand"],p["kind"],p["size_ml"],p["cost"],p["price"],p["stock"]])
    return Response("\ufeff"+output.getvalue(), mimetype="text/csv; charset=utf-8",
                    headers={"Content-Disposition":"attachment; filename=a_parfume_mehsullar.csv"})

if __name__ == "__main__":
    init_db()
    app.run(host="127.0.0.1", port=5000, debug=False)
