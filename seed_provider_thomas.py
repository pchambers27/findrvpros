import os, psycopg2, re
from psycopg2.extras import RealDictCursor
from datetime import date

def slugify(text):
    text = text.lower().strip()
    text = re.sub(r"[^a-z0-9]+", "-", text)
    return re.sub(r"-+", "-", text).strip("-")

DATABASE_URL = os.environ.get('DATABASE_URL', '')
if DATABASE_URL.startswith('postgres://'):
    DATABASE_URL = DATABASE_URL.replace('postgres://', 'postgresql://', 1)

conn = psycopg2.connect(DATABASE_URL)
cursor = conn.cursor(cursor_factory=RealDictCursor)

slug = "mission-mobile-rv-services"
cursor.execute("DELETE FROM providers WHERE slug = %s", (slug,))  # idempotent re-run

cursor.execute("""
    INSERT INTO providers
    (business_name, slug, contact_name, home_city, home_state, service_radius_mi,
     bio, insurance_verified, claimed, status, created_at)
    VALUES (%s, %s, %s, %s, %s, %s, %s, 0, 0, 'live', %s)
    RETURNING id
""", ("Mission Mobile RV Services", slug, "Thomas Geer", "Clearwater", "Florida", 50,
      None, date.today().isoformat()))
provider_id = cursor.fetchone()["id"]

# Offers: RV Inspection
cursor.execute("SELECT id FROM services WHERE slug = 'rv-inspection'")
service_id = cursor.fetchone()["id"]
cursor.execute("INSERT INTO provider_services (provider_id, service_id) VALUES (%s, %s) ON CONFLICT DO NOTHING",
            (provider_id, service_id))

# Serves: Clearwater (home) + Tampa + St. Petersburg (within 50 mi)
for city_slug in ("clearwater", "tampa", "st-petersburg"):
    cursor.execute("SELECT id FROM service_areas WHERE city_slug = %s", (city_slug,))
    area = cursor.fetchone()
    if area:
        cursor.execute("INSERT INTO provider_areas (provider_id, service_area_id) VALUES (%s, %s) ON CONFLICT DO NOTHING",
                    (provider_id, area["id"]))

# Credentials — UNVERIFIED. verified_at stays NULL until you confirm on the NRVIA locator.
cursor.execute("INSERT INTO credentials (provider_id, body, level, verified_at, source) VALUES (%s,%s,%s,%s,%s)",
            (provider_id, "NRVIA", "Certified Inspector", None, "to verify: nrvia locator"))
cursor.execute("INSERT INTO credentials (provider_id, body, level, verified_at, source) VALUES (%s,%s,%s,%s,%s)",
            (provider_id, "RVTAA", "Certified Technician", None, "to verify: rvtaa"))

conn.commit()
conn.close()
print("Seeded Mission Mobile RV Services (Thomas Geer) — credentials UNVERIFIED.")
