import sqlite3, re
from datetime import date

def slugify(text):
    text = text.lower().strip()
    text = re.sub(r"[^a-z0-9]+", "-", text)
    return re.sub(r"-+", "-", text).strip("-")

c = sqlite3.connect("app.db")
c.row_factory = sqlite3.Row
cur = c.cursor()

slug = "mission-mobile-rv-services"
cur.execute("DELETE FROM providers WHERE slug = ?", (slug,))  # idempotent re-run

cur.execute("""
    INSERT INTO providers
    (business_name, slug, contact_name, home_city, home_state, service_radius_mi,
     bio, insurance_verified, claimed, status, created_at)
    VALUES (?, ?, ?, ?, ?, ?, ?, 0, 0, 'live', ?)
""", ("Mission Mobile RV Services", slug, "Thomas Geer", "Clearwater", "Florida", 50,
      None, date.today().isoformat()))
provider_id = cur.lastrowid

# Offers: RV Inspection
service_id = cur.execute("SELECT id FROM services WHERE slug = 'rv-inspection'").fetchone()["id"]
cur.execute("INSERT OR IGNORE INTO provider_services (provider_id, service_id) VALUES (?, ?)",
            (provider_id, service_id))

# Serves: Clearwater (home) + Tampa + St. Petersburg (within 50 mi)
for city_slug in ("clearwater", "tampa", "st-petersburg"):
    area = cur.execute("SELECT id FROM service_areas WHERE city_slug = ?", (city_slug,)).fetchone()
    if area:
        cur.execute("INSERT OR IGNORE INTO provider_areas (provider_id, service_area_id) VALUES (?, ?)",
                    (provider_id, area["id"]))

# Credentials — UNVERIFIED. verified_at stays NULL until you confirm on the NRVIA locator.
cur.execute("INSERT INTO credentials (provider_id, body, level, verified_at, source) VALUES (?,?,?,?,?)",
            (provider_id, "NRVIA", "Certified Inspector", None, "to verify: nrvia locator"))
cur.execute("INSERT INTO credentials (provider_id, body, level, verified_at, source) VALUES (?,?,?,?,?)",
            (provider_id, "RVTAA", "Certified Technician", None, "to verify: rvtaa"))

c.commit(); c.close()
print("Seeded Mission Mobile RV Services (Thomas Geer) — credentials UNVERIFIED.")