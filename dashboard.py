
from http.server import HTTPServer, BaseHTTPRequestHandler
import json
import html
from urllib.parse import urlparse, parse_qs
from datetime import date

from core.database import (
    get_conn,
    init_db,
    export_to_csv,
    get_monthly_report,
    get_frequent_items
)

from core.utils import expiry_status, generate_chart_base64
from core.ai import ask_gemini, ask_offline

from core.auth import (
    init_auth,
    admin_exists,
    create_admin,
    verify_admin,
    create_session,
    get_session,
    delete_session
)


# ------------------------------------------
# COMMON HELPERS
# ------------------------------------------

def redirect_home(handler):
    handler.send_response(303)
    handler.send_header("Location", "/")
    handler.end_headers()


def safe(value):
    return html.escape(str(value or ""), quote=True)


# ------------------------------------------
# LOGIN / ADMIN SETUP PAGE
# ------------------------------------------

def render_auth_page(setup=False, error=""):

    title = "Create Your Admin Account" if setup else "Welcome Back"

    subtitle = (
        "Set up your secure FoodWise account"
        if setup
        else "Sign in to your FoodWise workspace"
    )

    action = "/setup" if setup else "/login"
    button = "Create Account" if setup else "Sign In"

    error_html = (
        f'<div class="error">{safe(error)}</div>'
        if error else ""
    )

    return f"""
    <!DOCTYPE html>
    <html>
    <head>
        <meta charset="UTF-8">
        <meta name="viewport" content="width=device-width, initial-scale=1">
        <title>FoodWise | Secure Access</title>

        <style>
            * {{
                box-sizing: border-box;
            }}

            body {{
                margin: 0;
                min-height: 100vh;
                display: grid;
                place-items: center;
                padding: 20px;
                font-family: -apple-system, BlinkMacSystemFont, sans-serif;
                color: #F3EBDD;
                background:
                    radial-gradient(circle at 15% 15%, #286B50, transparent 40%),
                    radial-gradient(circle at 85% 85%, #123B30, transparent 45%),
                    #071C17;
            }}

            .glass {{
                width: 100%;
                max-width: 420px;
                padding: 42px;
                border: 1px solid rgba(198,167,106,.35);
                border-radius: 28px;
                background: rgba(18,59,48,.72);
                backdrop-filter: blur(25px);
                -webkit-backdrop-filter: blur(25px);
                box-shadow: 0 25px 70px rgba(0,0,0,.35);
            }}

            .logo {{
                width: 65px;
                height: 65px;
                display: grid;
                place-items: center;
                margin: auto;
                border-radius: 20px;
                background: linear-gradient(135deg,#286B50,#C6A76A);
                font-size: 30px;
            }}

            h1 {{
                text-align: center;
                margin: 22px 0 8px;
                color: #F3EBDD;
            }}

            .subtitle {{
                text-align: center;
                color: #C6A76A;
                margin-bottom: 28px;
            }}

            label {{
                display: block;
                margin: 16px 0 7px;
                font-size: 14px;
            }}

            input {{
                width: 100%;
                padding: 14px;
                border: 1px solid rgba(198,167,106,.3);
                border-radius: 13px;
                background: rgba(7,28,23,.75);
                color: #F3EBDD;
                font-size: 15px;
                outline: none;
            }}

            input:focus {{
                border-color: #C6A76A;
            }}

            button {{
                width: 100%;
                padding: 15px;
                margin-top: 24px;
                border: 0;
                border-radius: 14px;
                background: linear-gradient(135deg,#286B50,#C6A76A);
                color: #071C17;
                font-size: 16px;
                font-weight: 700;
                cursor: pointer;
            }}

            button:hover {{
                filter: brightness(1.1);
            }}

            .error {{
                padding: 12px;
                border-radius: 12px;
                background: rgba(180,50,50,.2);
                color: #ffb7b7;
                margin-bottom: 15px;
            }}

            .footer {{
                text-align: center;
                color: #C6A76A;
                font-size: 11px;
                margin-top: 24px;
                letter-spacing: 1px;
            }}
        </style>
    </head>

    <body>
        <main class="glass">

            <div class="logo">🍎</div>

            <h1>FoodWise</h1>

            <p class="subtitle">{subtitle}</p>

            {error_html}

            <form method="POST" action="{action}">

                <label>Username</label>

                <input
                    name="username"
                    minlength="3"
                    autocomplete="username"
                    required
                >

                <label>Password</label>

                <input
                    type="password"
                    name="password"
                    minlength="8"
                    autocomplete="current-password"
                    required
                >

                <button type="submit">{button}</button>

            </form>

            <div class="footer">
                FOODWISE · SMART GROCERY MANAGEMENT
            </div>

        </main>
    </body>
    </html>
    """.encode("utf-8")


# ------------------------------------------
# MAIN FOODWISE DASHBOARD
# ------------------------------------------

def render_html(search_query="", edit_id=None):

    conn = get_conn()

    if search_query:
        items = conn.execute(
            "SELECT * FROM items WHERE LOWER(name) LIKE ? ORDER BY name",
            (f"%{search_query.lower()}%",)
        ).fetchall()
    else:
        items = conn.execute(
            "SELECT * FROM items ORDER BY name"
        ).fetchall()

    edit_item = None

    if edit_id:
        edit_item = conn.execute(
            "SELECT * FROM items WHERE id = ?",
            (edit_id,)
        ).fetchone()

    conn.close()

    total_items = len(items)

    expiring = sum(
        1 for item in items
        if item["expiry_date"]
        and expiry_status(item["expiry_date"])[1] in ["orange", "red"]
    )

    report = get_monthly_report()
    frequent = get_frequent_items()
    chart_img = generate_chart_base64()

    # Inventory table
    rows = ""

    for item in items:

        label, color = expiry_status(item["expiry_date"])

        rows += f"""
        <tr>
            <td>{safe(item['name'])}</td>
            <td>{safe(item['category'])}</td>
            <td>{item['quantity']} {safe(item['unit'])}</td>
            <td>₹{item['price']}</td>
            <td>{safe(item['expiry_date'] or '—')}</td>
            <td class="{safe(color)}">{safe(label)}</td>
            <td class="actions">
                <a href="/?edit={item['id']}">Edit</a>
                <a href="/delete/{item['id']}"
                   onclick="return confirm('Delete this item?')">
                   Delete
                </a>
            </td>
        </tr>
        """

    # Edit form
    edit_form_html = ""

    if edit_item:
        edit_form_html = f"""
        <section class="glass-panel">
            <h2>✏️ Edit Inventory Item</h2>

            <form method="POST" action="/update_item">
                <input type="hidden" name="id"
                       value="{edit_item['id']}">

                <input name="name"
                       value="{safe(edit_item['name'])}"
                       placeholder="Item name" required>

                <input name="category"
                       value="{safe(edit_item['category'])}"
                       placeholder="Category" required>

                <input type="number" step="0.01" name="qty"
                       value="{edit_item['quantity']}" required>

                <input type="number" step="0.01" name="price"
                       value="{edit_item['price']}" required>

                <input name="expiry"
                       value="{safe(edit_item['expiry_date'])}"
                       placeholder="Expiry YYYY-MM-DD">

                <button type="submit">Save Changes</button>
            </form>
        </section>
        """

    # Monthly report lists
    freq_rows = "".join(
        f"<li>{safe(item['item_name'])} (x{item['n']})</li>"
        for item in frequent
    )

    cat_rows = "".join(
        f"<li>{safe(item['category'])}: ₹{item['s']}</li>"
        for item in report["by_cat"]
    )

    chart_html = (
        f'<img src="data:image/png;base64,{chart_img}" alt="Stock chart">'
        if chart_img else "<p>No stock data available.</p>"
    )

    html_page = f"""
    <!DOCTYPE html>
    <html lang="en">

    <head>
        <meta charset="UTF-8">
        <meta name="viewport" content="width=device-width, initial-scale=1">

        <title>FoodWise | Dashboard</title>

        <style>

            * {{
                box-sizing: border-box;
            }}

            body {{
                margin: 0;
                padding: 25px 30px 40px 285px;
                min-height: 100vh;
                font-family: -apple-system, BlinkMacSystemFont, "Segoe UI", sans-serif;
                color: #F3EBDD;
                background:
                    radial-gradient(circle at 85% 10%, rgba(40,107,80,.25), transparent 30%),
                    radial-gradient(circle at 10% 90%, rgba(198,167,106,.10), transparent 30%),
                    #071C17;
            }}

            .sidebar {{
                position: fixed;
                top: 20px;
                left: 20px;
                bottom: 20px;
                width: 240px;
                padding: 25px 18px;
                display: flex;
                flex-direction: column;
                justify-content: space-between;
                border: 1px solid rgba(198,167,106,.25);
                border-radius: 24px;
                background: rgba(18,59,48,.78);
                backdrop-filter: blur(22px);
                -webkit-backdrop-filter: blur(22px);
                box-shadow: 0 15px 45px rgba(0,0,0,.25);
                z-index: 10;
            }}

            .brand {{
                font-size: 25px;
                font-weight: 800;
                color: #F3EBDD;
                margin-bottom: 5px;
            }}

            .brand span {{
                color: #C6A76A;
            }}

            .sidebar p {{
                color: #b8c9bd;
                font-size: 12px;
                margin-bottom: 30px;
            }}

            .sidebar a {{
                display: block;
                padding: 13px;
                margin: 8px 0;
                border-radius: 12px;
                text-decoration: none;
                color: #F3EBDD;
                transition: .2s;
            }}

            .sidebar a:hover {{
                background: rgba(198,167,106,.15);
                color: #C6A76A;
                transform: translateX(3px);
            }}

            .logout {{
                color: #e9b5a9 !important;
            }}

            .topbar {{
                display: flex;
                align-items: center;
                justify-content: space-between;
                gap: 15px;
                flex-wrap: wrap;
                margin-bottom: 30px;
            }}

            .topbar h1 {{
                margin: 0;
                font-size: 30px;
            }}

            .topbar p {{
                color: #b8c9bd;
                margin: 7px 0 0;
            }}

            .date-label {{
                padding: 12px 16px;
                border: 1px solid rgba(198,167,106,.3);
                border-radius: 14px;
                color: #C6A76A;
                background: rgba(18,59,48,.6);
            }}

            .glass-panel {{
                padding: 23px;
                border: 1px solid rgba(198,167,106,.22);
                border-radius: 21px;
                background: rgba(18,59,48,.58);
                backdrop-filter: blur(18px);
                -webkit-backdrop-filter: blur(18px);
                box-shadow: 0 12px 35px rgba(0,0,0,.16);
                margin-bottom: 22px;
                min-width: 0;
            }}

            .stats {{
                display: grid;
                grid-template-columns: repeat(3, minmax(0, 1fr));
                gap: 18px;
                margin-bottom: 22px;
            }}

            .stat-card {{
                padding: 22px;
                border: 1px solid rgba(198,167,106,.22);
                border-radius: 20px;
                background: linear-gradient(145deg, rgba(18,59,48,.9), rgba(7,28,23,.85));
            }}

            .stat-card p {{
                color: #b8c9bd;
                margin: 0 0 10px;
            }}

            .stat-card h2 {{
                color: #C6A76A;
                font-size: 30px;
                margin: 0;
            }}

            .section-grid {{
                display: grid;
                grid-template-columns: repeat(2, minmax(0, 1fr));
                gap: 20px;
            }}

            h2 {{
                margin-top: 0;
                color: #F3EBDD;
            }}

            h3 {{
                color: #C6A76A;
                margin-top: 0;
            }}

            input {{
                width: 100%;
                padding: 13px 14px;
                margin: 7px 0;
                border: 1px solid rgba(198,167,106,.2);
                border-radius: 12px;
                background: rgba(7,28,23,.8);
                color: #F3EBDD;
                outline: none;
                font-size: 14px;
            }}

            input:focus {{
                border-color: #C6A76A;
            }}

            input::placeholder {{
                color: #91a69a;
            }}

            button {{
                width: 100%;
                padding: 13px;
                margin-top: 10px;
                border: 0;
                border-radius: 12px;
                background: linear-gradient(135deg,#286B50,#C6A76A);
                color: #071C17;
                font-size: 14px;
                font-weight: 700;
                cursor: pointer;
                transition: .2s;
            }}

            button:hover {{
                transform: translateY(-2px);
                filter: brightness(1.08);
            }}

            .search-form {{
                display: flex;
                gap: 10px;
                max-width: 550px;
            }}

            .search-form input {{
                flex: 1;
            }}

            .search-form button {{
                width: 120px;
                margin-top: 7px;
            }}

            .table-wrap {{
                overflow-x: auto;
            }}

            table {{
                width: 100%;
                border-collapse: collapse;
                min-width: 700px;
            }}

            th, td {{
                padding: 15px 12px;
                text-align: left;
                border-bottom: 1px solid rgba(198,167,106,.14);
            }}

            th {{
                color: #C6A76A;
                font-size: 13px;
                font-weight: 700;
            }}

            td {{
                color: #E9E9DF;
                font-size: 13px;
            }}

            .actions a {{
                display: inline-block;
                margin: 3px;
                text-decoration: none;
                color: #C6A76A;
                font-weight: 600;
            }}

            .actions a:last-child {{
                color: #e9a39a;
            }}

            .green {{
                color: #80d6a4;
            }}

            .orange {{
                color: #e9bc75;
            }}

            .red {{
                color: #ff8f83;
            }}

            .gray {{
                color: #b8c9bd;
            }}

            ul {{
                padding-left: 20px;
                color: #d5e0d8;
                line-height: 1.9;
            }}

            .chart-image {{
                width: 100%;
                border-radius: 14px;
                background: #F3EBDD;
            }}

            .ai-answer {{
                color: #C6A76A;
                white-space: pre-wrap;
                line-height: 1.6;
            }}

            .footer {{
                text-align: center;
                color: #789184;
                font-size: 12px;
                margin-top: 35px;
            }}

            @media(max-width: 950px) {{
                body {{
                    padding-left: 25px;
                }}

                .sidebar {{
                    position: relative;
                    width: 100%;
                    height: auto;
                    top: auto;
                    left: auto;
                    bottom: auto;
                    margin-bottom: 25px;
                    gap: 15px;
                }}

                .stats {{
                    grid-template-columns: repeat(2, minmax(0, 1fr));
                }}
            }}

            @media(max-width: 650px) {{
                body {{
                    padding: 15px;
                }}

                .section-grid,
                .stats {{
                    grid-template-columns: 1fr;
                }}

                .topbar h1 {{
                    font-size: 24px;
                }}

                .search-form {{
                    flex-direction: column;
                }}

                .search-form button {{
                    width: 100%;
                }}

                .glass-panel {{
                    padding: 17px;
                }}
            }}

        </style>
    </head>

    <body>

        <aside class="sidebar">

            <div>
                <div class="brand">🍎 Food<span>Wise</span></div>
                <p>SMART GROCERY MANAGEMENT</p>

                <a href="/">⌂ &nbsp; Dashboard</a>
                <a href="#inventory">▤ &nbsp; Inventory</a>
                <a href="#purchase">🛒 &nbsp; Purchases</a>
                <a href="#reports">▥ &nbsp; Reports</a>
                <a href="#assistant">✦ &nbsp; AI Assistant</a>
                <a href="/export">↓ &nbsp; Export CSV</a>
            </div>

            <a class="logout" href="/logout">⇥ &nbsp; Logout</a>

        </aside>

        <main>

            <header class="topbar">
                <div>
                    <h1>Dashboard Overview</h1>
                    <p>Manage your groceries, stock and spending.</p>
                </div>

                <div class="date-label">
                    📅 {date.today().strftime("%d %B %Y")}
                </div>
            </header>

            <section class="stats">

                <div class="stat-card">
                    <p>Total Inventory Items</p>
                    <h2>{total_items}</h2>
                </div>

                <div class="stat-card">
                    <p>Expiring / Expired</p>
                    <h2>{expiring}</h2>
                </div>

                <div class="stat-card">
                    <p>This Month Spending</p>
                    <h2>₹{report['total']}</h2>
                </div>

            </section>

            <section class="glass-panel">
                <h3>⌕ Search Inventory</h3>

                <form class="search-form" method="GET" action="/">
                    <input
                        name="q"
                        placeholder="Search grocery items..."
                        value="{safe(search_query)}"
                    >

                    <button type="submit">Search</button>
                </form>
            </section>

            {edit_form_html}

            <section class="section-grid">

                <div class="glass-panel">
                    <h3>＋ Add New Item</h3>

                    <form method="POST" action="/add_item">

                        <input name="name"
                               placeholder="Item Name"
                               required>

                        <input name="category"
                               placeholder="Category"
                               required>

                        <input type="number"
                               step="0.01"
                               min="0.01"
                               name="qty"
                               placeholder="Quantity"
                               required>

                        <input type="number"
                               step="0.01"
                               min="0"
                               name="price"
                               placeholder="Price"
                               required>

                        <input type="date" name="expiry">

                        <button type="submit">Add to Inventory</button>

                    </form>
                </div>

                <div class="glass-panel" id="purchase">
                    <h3>🛒 Record Purchase</h3>

                    <form method="POST" action="/record_purchase">

                        <input name="name"
                               placeholder="Item Name"
                               required>

                        <input type="number"
                               step="0.01"
                               min="0.01"
                               name="qty"
                               placeholder="Quantity"
                               required>

                        <input type="number"
                               step="0.01"
                               min="0.01"
                               name="price"
                               placeholder="Total Purchase Price"
                               required>

                        <button type="submit">Save Purchase</button>

                    </form>
                </div>

                <div class="glass-panel" id="reports">
                    <h3>📈 Monthly Expense Report</h3>

                    <h2>₹{report['total']}</h2>

                    <h3>Spending by Category</h3>

                    <ul>
                        {cat_rows if cat_rows else "<li>No purchase data yet</li>"}
                    </ul>

                    <h3>Frequently Purchased</h3>

                    <ul>
                        {freq_rows if freq_rows else "<li>No purchase history yet</li>"}
                    </ul>
                </div>

                <div class="glass-panel">
                    <h3>📊 Stock Overview</h3>
                    {chart_html}
                </div>

            </section>

            <section class="glass-panel" id="inventory">

                <h2>Inventory Management</h2>

                <div class="table-wrap">
                    <table>

                        <thead>
                            <tr>
                                <th>Item</th>
                                <th>Category</th>
                                <th>Quantity</th>
                                <th>Price</th>
                                <th>Expiry Date</th>
                                <th>Status</th>
                                <th>Actions</th>
                            </tr>
                        </thead>

                        <tbody>
                            {rows if rows else '<tr><td colspan="7">No inventory items found.</td></tr>'}
                        </tbody>

                    </table>
                </div>

            </section>

            <section class="glass-panel" id="assistant">

                <h2>✦ FoodWise AI Assistant</h2>

                <p>Ask questions about your grocery inventory and purchases.</p>

                <input
                    id="question"
                    placeholder="Example: Which items are expiring soon?"
                >

                <button onclick="askAI()">Ask FoodWise AI</button>

                <p id="answer" class="ai-answer"></p>

            </section>

            <footer class="footer">
                FOODWISE · SMART GROCERY MANAGEMENT SYSTEM
            </footer>

        </main>

        <script>

            async function askAI() {{

                const question = document.getElementById("question").value;
                const output = document.getElementById("answer");

                if (!question.trim()) {{
                    output.innerText = "Please enter a question.";
                    return;
                }}

                output.innerText = "FoodWise AI is thinking...";

                try {{

                    const response = await fetch("/api/ai", {{

                        method: "POST",

                        headers: {{
                            "Content-Type": "application/json"
                        }},

                        body: JSON.stringify({{
                            question: question
                        }})

                    }});

                    if (!response.ok) {{
                        throw new Error("Request failed");
                    }}

                    const data = await response.json();

                    output.innerText =
                        data.answer || data.error || "No response received.";

                }} catch (error) {{

                    output.innerText = "AI request failed. Please try again.";

                }}

            }}

        </script>

    </body>
    </html>
    """

    return html_page.encode("utf-8")


class RequestHandler(BaseHTTPRequestHandler):

    def send_page(self, content, status=200, cookie=None):
        self.send_response(status)
        self.send_header("Content-Type", "text/html; charset=utf-8")

        if cookie:
            self.send_header("Set-Cookie", cookie)

        self.end_headers()
        self.wfile.write(content)

    def get_current_user(self):
        cookies = self.headers.get("Cookie", "")
        token = None

        for part in cookies.split(";"):
            key, separator, value = part.strip().partition("=")

            if key == "foodwise_session":
                token = value
                break

        if not token:
            return None

        return get_session(token)

    def require_login(self):
        if self.get_current_user():
            return True

        self.send_response(303)
        self.send_header("Location", "/")
        self.end_headers()
        return False

    def redirect(self, location="/"):
        self.send_response(303)
        self.send_header("Location", location)
        self.end_headers()

    def do_GET(self):

        parsed = urlparse(self.path)
        path = parsed.path

        # Logout
        if path == "/logout":
            cookies = self.headers.get("Cookie", "")
            token = None

            for part in cookies.split(";"):
                key, separator, value = part.strip().partition("=")

                if key == "foodwise_session":
                    token = value
                    break

            if token:
                delete_session(token)

            self.send_response(303)
            self.send_header(
                "Set-Cookie",
                "foodwise_session=; Path=/; Max-Age=0; HttpOnly; SameSite=Lax"
            )
            self.send_header("Location", "/")
            self.end_headers()
            return

        # First-time setup and login
        if path == "/":
            if not admin_exists():
                self.send_page(render_auth_page(setup=True))
                return

            if not self.get_current_user():
                self.send_page(render_auth_page())
                return

            params = parse_qs(parsed.query)
            search_query = params.get("q", [""])[0]
            edit_id = params.get("edit", [None])[0]

            try:
                content = render_html(search_query, edit_id)
                self.send_page(content)
            except Exception as error:
                print("Dashboard Error:", error)
                self.send_error(500, "Unable to load dashboard")

            return

        # All remaining GET routes require login
        if not self.require_login():
            return

        # CSV Export
        if path == "/export":
            try:
                filename = export_to_csv("exported_data.csv")

                self.send_response(200)
                self.send_header(
                    "Content-Type",
                    "text/plain; charset=utf-8"
                )
                self.end_headers()

                self.wfile.write(
                    f"CSV exported successfully: {filename}".encode("utf-8")
                )

            except Exception as error:
                print("Export Error:", error)
                self.send_error(500, "CSV export failed")

            return

        # Delete item
        if path.startswith("/delete/"):
            conn = None

            try:
                item_id = int(path.split("/")[-1])

                if item_id <= 0:
                    raise ValueError("Invalid item ID")

                conn = get_conn()

                conn.execute(
                    "DELETE FROM items WHERE id = ?",
                    (item_id,)
                )

                conn.commit()
                self.redirect()

            except (ValueError, TypeError):
                self.send_error(400, "Invalid item ID")

            except Exception as error:
                print("Delete Error:", error)
                self.send_error(500, "Unable to delete item")

            finally:
                if conn:
                    conn.close()

            return

        self.send_error(404, "Page not found")

    def do_POST(self):

        path = urlparse(self.path).path

        try:
            length = int(self.headers.get("Content-Length", 0))

            if length > 1000000:
                self.send_error(413, "Request too large")
                return

            body = self.rfile.read(length)

            # Read login/setup form data
            if path in ["/setup", "/login"]:
                form = parse_qs(body.decode("utf-8"))

                username = form.get("username", [""])[0].strip()
                password = form.get("password", [""])[0]

                # First-time admin setup
                if path == "/setup":

                    if admin_exists():
                        self.send_page(
                            render_auth_page(
                                error="Admin account already exists."
                            ),
                            403
                        )
                        return

                    success, message = create_admin(username, password)

                    if not success:
                        self.send_page(
                            render_auth_page(
                                setup=True,
                                error=message
                            ),
                            400
                        )
                        return

                    token = create_session(username)

                    self.send_response(303)
                    self.send_header(
                        "Set-Cookie",
                        f"foodwise_session={token}; Path=/; HttpOnly; SameSite=Lax; Max-Age=28800"
                    )
                    self.send_header("Location", "/")
                    self.end_headers()
                    return

                # Login
                if path == "/login":

                    if not admin_exists():
                        self.redirect("/")
                        return

                    if not verify_admin(username, password):
                        self.send_page(
                            render_auth_page(
                                error="Invalid username or password."
                            ),
                            401
                        )
                        return

                    token = create_session(username)

                    self.send_response(303)
                    self.send_header(
                        "Set-Cookie",
                        f"foodwise_session={token}; Path=/; HttpOnly; SameSite=Lax; Max-Age=28800"
                    )
                    self.send_header("Location", "/")
                    self.end_headers()
                    return

            # All other POST routes require login
            if not self.require_login():
                return

            # AI API receives JSON
            if path == "/api/ai":

                data = json.loads(body.decode("utf-8"))
                question = data.get("question", "").strip()

                if not question:
                    self.send_error(400, "Question is required")
                    return

                answer, error = ask_gemini(question)

                if error:
                    print("Gemini Error:", error)
                    answer = ask_offline(question)

                result = {
                    "answer": answer,
                    "mode": "offline" if error else "online",
                    "error": None
                }

                self.send_response(200)
                self.send_header(
                    "Content-Type",
                    "application/json; charset=utf-8"
                )
                self.end_headers()

                self.wfile.write(
                    json.dumps(result).encode("utf-8")
                )
                return

            # Read normal form data
            form = parse_qs(body.decode("utf-8"))

            # Add item
            if path == "/add_item":

                name = form.get("name", [""])[0].strip()
                category = form.get("category", [""])[0].strip()
                qty = float(form.get("qty", ["0"])[0])
                price = float(form.get("price", ["0"])[0])
                expiry = form.get("expiry", [""])[0].strip() or None

                if not name or not category or qty <= 0 or price < 0:
                    self.send_error(400, "Invalid item details")
                    return

                conn = get_conn()

                try:
                    conn.execute(
                        """
                        INSERT INTO items
                        (name, category, quantity, unit, price,
                         expiry_date, added_date)
                        VALUES (?, ?, ?, ?, ?, ?, ?)
                        """,
                        (
                            name,
                            category,
                            qty,
                            "pcs",
                            price,
                            expiry,
                            date.today().isoformat()
                        )
                    )

                    conn.commit()
                finally:
                    conn.close()

                self.redirect()
                return

            # Update item
            elif path == "/update_item":

                item_id = int(form.get("id", ["0"])[0])
                name = form.get("name", [""])[0].strip()
                category = form.get("category", [""])[0].strip()
                qty = float(form.get("qty", ["0"])[0])
                price = float(form.get("price", ["0"])[0])
                expiry = form.get("expiry", [""])[0].strip() or None

                if (
                    item_id <= 0
                    or not name
                    or not category
                    or qty <= 0
                    or price < 0
                ):
                    self.send_error(400, "Invalid item details")
                    return

                conn = get_conn()

                try:
                    conn.execute(
                        """
                        UPDATE items
                        SET name = ?, category = ?, quantity = ?,
                            price = ?, expiry_date = ?
                        WHERE id = ?
                        """,
                        (name, category, qty, price, expiry, item_id)
                    )

                    conn.commit()
                finally:
                    conn.close()

                self.redirect()
                return

            # Record purchase
            elif path == "/record_purchase":

                name = form.get("name", [""])[0].strip()
                qty = float(form.get("qty", ["0"])[0])
                price = float(form.get("price", ["0"])[0])

                if not name or qty <= 0 or price <= 0:
                    self.send_error(400, "Invalid purchase details")
                    return

                conn = get_conn()

                try:
                    item = conn.execute(
                        """
                        SELECT category
                        FROM items
                        WHERE LOWER(name) = LOWER(?)
                        LIMIT 1
                        """,
                        (name,)
                    ).fetchone()

                    category = item[0] if item else "Other"

                    conn.execute(
                        """
                        INSERT INTO purchases
                        (item_name, category, quantity, price, purchase_date)
                        VALUES (?, ?, ?, ?, ?)
                        """,
                        (
                            name,
                            category,
                            qty,
                            price,
                            date.today().isoformat()
                        )
                    )

                    conn.commit()
                finally:
                    conn.close()

                self.redirect()
                return

            else:
                self.send_error(404, "Route not found")

        except (ValueError, TypeError, json.JSONDecodeError) as error:
            self.send_error(400, str(error))

        except Exception as error:
            print("Server Error:", error)
            self.send_error(500, "Internal server error")

    def log_message(self, format, *args):
        pass


def run_server(port=8000):

    init_db()
    init_auth()

    server = HTTPServer(
        ("127.0.0.1", port),
        RequestHandler
    )

    print(f"\nFoodWise Dashboard running at http://localhost:{port}\n")

    try:
        server.serve_forever()

    except KeyboardInterrupt:
        print("\nFoodWise Dashboard stopped.")

    finally:
        server.server_close()


if __name__ == "__main__":
    run_server()
