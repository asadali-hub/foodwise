# 🍎 FoodWise — Smart Food & Grocery Tracker

**FoodWise** is a fully functional, pure Python application designed to manage your kitchen inventory, track expenses, and reduce food waste. 

It features **both** a Terminal-based Command Line Interface (CLI) and a modern Web Dashboard, all built **without using any external web frameworks** like Flask or Django.

---

## ✨ Features

- **Dual Interface:** 
  - Interactive Terminal Menu (CLI).
  - Modern Web Dashboard (runs on `http://localhost:8000`).
- **Smart AI Assistant:** Integrated with Google Gemini API (Online) with a robust Rule-based fallback (Offline).
- **Inventory Management:** Add, update, delete, and search grocery items.
- **Expiry Tracking:** Automatically calculates and highlights expiring/expired items.
- **Expense Tracking:** Record purchases and generate monthly expenditure reports.
- **Data Export:** Export your entire inventory to a CSV file.
- **Visual Charts:** Generates stock charts using `matplotlib`.
- **Zero HTML/CSS/JS Files:** The web interface is rendered entirely via Python strings using `http.server`.

---

## 📦 Standard Libraries Used

This project strictly uses Python's standard libraries to demonstrate core programming concepts:

- `sqlite3` — Database management
- `http.server` & `urllib.parse` — Web server and form parsing
- `csv` — Data export
- `json` — AI API communication
- `re` — Input validation (Regex)
- `logging` — Error tracking (`foodwise.log`)
- `datetime` — Expiry date calculations
- `base64` & `io` — Image encoding for charts

---

## 🛠️ Installation & Setup

