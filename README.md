# Pink Attic Inventory Tracker

A web-based inventory and sales tracking application designed for resellers to manage purchased items, active listings, and sold items in one place.

Built with Flask and SQLAlchemy, this tool allows users to create accounts, categorize inventory, track costs and profits, and eventually import active eBay listings.

---

##  Features (Current & Planned)

###  Current / MVP (in progress)
- User registration & login
- Add inventory items with:
  - Cost
  - Source
  - Purchase date
  - Category
- Mark items as sold with:
  - Sold date
  - Selling platform
  - Sold price
  - Shipping Cost
  - Notes/Fees
- Filter and search inventory

###  Planned
- CSV import for bulk item entry
- eBay active listings import (API integration)
- Profit & reporting dashboard
- Item photos
- Multi-platform selling support (Etsy, Poshmark, etc.)

---

##  Tech Stack

- Python
- Flask
- Flask-SQLAlchemy
- Flask-Login
- SQLite (development)
- HTML/CSS (Jinja templates)

---

##  Project Structure

pinkattic_tracker/
│ run.py
│ requirements.txt
│ README.md
└─ app/
├─ init.py
├─ models.py
└─ routes/




