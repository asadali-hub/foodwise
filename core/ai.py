
from pathlib import Path

from google import genai
from .logger import logger
from .database import get_conn, get_monthly_report, get_frequent_items


# config.txt is located in the main FoodWise project folder
CONFIG_FILE = Path(__file__).resolve().parent.parent / "config.txt"

GEMINI_MODEL = "gemini-3.8-flash"


def load_api_key():
    """Read Gemini API key from config.txt."""
    try:
        if not CONFIG_FILE.exists():
            logger.error("config.txt file not found")
            return None

        with open(CONFIG_FILE, "r", encoding="utf-8") as file:
            for line in file:
                line = line.strip()

                if line.startswith("GEMINI_API_KEY="):
                    key = line.split("=", 1)[1].strip()
                    return key.strip('"').strip("'") or None

    except Exception as e:
        logger.error(f"Error reading API key: {e}")

    return None


def ask_gemini(question):
    """Send a question to Gemini AI."""
    key = load_api_key()

    if not key:
        return None, "No API key found in config.txt"

    try:
        client = genai.Client(api_key=key)

        prompt = f"""
        You are FoodWise, a smart grocery inventory assistant.
        Answer clearly and concisely.
        Help users with grocery inventory, food expiry,
        shopping and food management.

        User question: {question}
        """

        response = client.models.generate_content(
            model=GEMINI_MODEL,
            contents=prompt
        )

        if response.text:
            return response.text.strip(), None

        return None, "Empty response from Gemini"

    except Exception as e:
        error_msg = f"Gemini API Error: {str(e)}"
        logger.error(error_msg)
        return None, error_msg


def ask_offline(question):
    """Answer common grocery questions using SQLite."""

    q = question.lower().strip()
    conn = get_conn()

    try:

        # 1. Expiring products
        if "expir" in q:
            rows = conn.execute("""
                SELECT name, expiry_date
                FROM items
                WHERE expiry_date IS NOT NULL
                AND date(expiry_date) <= date('now', '+7 day')
                ORDER BY date(expiry_date)
            """).fetchall()

            if not rows:
                return "Everything is fresh! Nothing is expiring soon."

            return "Expiring soon:\n" + "\n".join(
                [f"• {r['name']} (Expires: {r['expiry_date']})"
                 for r in rows]
            )

        # 2. Monthly spending
        if "spend" in q or "spent" in q:
            report = get_monthly_report()
            return f"Total spend for this month: ₹{report['total']}"

        # 3. Highest quantity (including ties)
        if (
            "highest quantity" in q
            or "maximum quantity" in q
            or "most quantity" in q
            or "highest stock" in q
        ):
            rows = conn.execute("""
                WITH stock AS (
                    SELECT
                        MIN(name) AS name,
                        SUM(quantity) AS total
                    FROM items
                    GROUP BY LOWER(name)
                )
                SELECT name, total
                FROM stock
                WHERE total = (SELECT MAX(total) FROM stock)
            """).fetchall()

            if not rows:
                return "No inventory items found."

            return "Highest quantity in stock:\n" + "\n".join(
                [f"• {r['name']}: {r['total']} units"
                 for r in rows]
            )

        # 4. Frequently purchased items
        if "frequent" in q or "buy most" in q:
            freq = get_frequent_items()

            if not freq:
                return "No purchase history found yet."

            return "Most frequently purchased items:\n" + "\n".join(
                [f"• {f['item_name']} (Bought {f['n']} times)"
                 for f in freq]
            )

        # 5. Total number of products
        if "how many" in q or "total products" in q:
            result = conn.execute(
                "SELECT COUNT(*) AS c FROM items"
            ).fetchone()

            return f"You have {result['c']} total products in stock."

        # 6. Low stock products
        if "low" in q or "running out" in q:
            rows = conn.execute("""
                SELECT name, quantity
                FROM items
                WHERE quantity <= 1
            """).fetchall()

            if not rows:
                return "You have sufficient stock for all items."

            return "Items running low:\n" + "\n".join(
                [f"• {r['name']}: Only {r['quantity']} left"
                 for r in rows]
            )

        # 7. Check a specific product
        if "do i have" in q or "have " in q:
            keyword = (
                q.replace("do i have", "")
                 .replace("have", "")
                 .replace("?", "")
                 .strip()
            )

            if not keyword:
                return "Please mention an item name, like 'Do I have milk?'"

            rows = conn.execute("""
                SELECT name, SUM(quantity) AS total
                FROM items
                WHERE LOWER(name) LIKE ?
                GROUP BY LOWER(name)
            """, (f"%{keyword}%",)).fetchall()

            if not rows:
                return f"I couldn't find any item matching '{keyword}'."

            return "Found in your inventory:\n" + "\n".join(
                [f"• {r['name']}: {r['total']} in stock"
                 for r in rows]
            )

        return (
            "I didn't understand that. Try asking:\n"
            "• What's expiring soon?\n"
            "• How much did I spend this month?\n"
            "• Which item has the highest quantity?\n"
            "• Do I have milk?\n"
            "• Which items are low in stock?\n"
            "• How many products do I have?"
        )

    except Exception as e:
        logger.error(f"Offline AI Error: {e}")
        return "Sorry, I couldn't process that question."

    finally:
        conn.close()
