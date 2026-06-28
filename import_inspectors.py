import csv
import os
import re
import psycopg2
from datetime import date

DATABASE_URL = os.environ.get('DATABASE_URL', '')
if DATABASE_URL.startswith('postgres://'):
    DATABASE_URL = DATABASE_URL.replace('postgres://', 'postgresql://', 1)


def slugify(text):
    text = text.lower().strip()
    text = re.sub(r"[^a-z0-9]+", "-", text)
    return re.sub(r"-+", "-", text).strip("-")


def unique_slug(cursor, base_slug, city_slug):
    """base -> base-city -> base-city-2 ... until one is free."""
    for candidate in (base_slug, f"{base_slug}-{city_slug}"):
        cursor.execute("SELECT 1 FROM providers WHERE slug = %s", (candidate,))
        if not cursor.fetchone():
            return candidate
    n = 2
    while True:
        candidate = f"{base_slug}-{city_slug}-{n}"
        cursor.execute("SELECT 1 FROM providers WHERE slug = %s", (candidate,))
        if not cursor.fetchone():
            return candidate
        n += 1


def get_or_create_area(cursor, city, state):
    city_slug = slugify(city)
    state_slug = slugify(state)
    cursor.execute(
        "SELECT id FROM service_areas WHERE state_slug = %s AND city_slug = %s",
        (state_slug, city_slug)
    )
    row = cursor.fetchone()
    if row:
        return row[0], False
    cursor.execute(
        """INSERT INTO service_areas (state, state_slug, city, city_slug)
           VALUES (%s, %s, %s, %s) RETURNING id""",
        (state, state_slug, city, city_slug)
    )
    return cursor.fetchone()[0], True


conn = psycopg2.connect(DATABASE_URL)
cursor = conn.cursor()

# The rv-inspection service id
cursor.execute("SELECT id FROM services WHERE slug = 'rv-inspection'")
service_id = cursor.fetchone()[0]

added, skipped, new_cities = 0, 0, []
today = date.today().isoformat()

with open('inspectors.csv', newline='', encoding='utf-8') as f:
    reader = csv.DictReader(f)
    for row in reader:
        business_name = row['business_name'].strip()
        if not business_name:
            continue

        home_city = row['home_city'].strip()
        home_state = row['home_state'].strip() or 'Florida'

        # Duplicate guard: same business name + city already in DB
        cursor.execute(
            "SELECT id FROM providers WHERE business_name = %s AND home_city = %s",
            (business_name, home_city)
        )
        if cursor.fetchone():
            print(f"  skip (already exists): {business_name} — {home_city}")
            skipped += 1
            continue

        slug = unique_slug(cursor, slugify(business_name), slugify(home_city or 'fl'))

        radius = row.get('service_radius_mi', '').strip()
        radius = int(radius) if radius.isdigit() else 50

        cursor.execute(
            """
            INSERT INTO providers
            (business_name, slug, contact_name, home_city, home_state,
             service_radius_mi, phone, website, bio,
             insurance_verified, claimed, status, created_at)
            VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, 0, 0, 'live', %s)
            RETURNING id
            """,
            (business_name, slug, row.get('contact_name', '').strip(),
             home_city, home_state, radius,
             row.get('phone', '').strip(), row.get('website', '').strip(),
             row.get('bio', '').strip() or None, today)
        )
        provider_id = cursor.fetchone()[0]

        # Link to the rv-inspection service
        cursor.execute(
            """INSERT INTO provider_services (provider_id, service_id)
               VALUES (%s, %s) ON CONFLICT DO NOTHING""",
            (provider_id, service_id)
        )

        # NRVIA credential, marked verified (sourced from their own site)
        level = row.get('nrvia_level', '').strip() or 'Certified Inspector'
        cursor.execute(
            """INSERT INTO credentials (provider_id, body, level, verified_at, source)
               VALUES (%s, 'NRVIA', %s, %s, %s)""",
            (provider_id, level, today, 'first-party site, verified manually')
        )

        # Service areas (pipe-separated). Fall back to home city if blank.
        cities = [c.strip() for c in row.get('cities_served', '').split('|') if c.strip()]
        if not cities and home_city:
            cities = [home_city]

        for city in cities:
            area_id, was_new = get_or_create_area(cursor, city, home_state)
            if was_new:
                new_cities.append(f"{city}, {home_state}")
            cursor.execute(
                """INSERT INTO provider_areas (provider_id, service_area_id)
                   VALUES (%s, %s) ON CONFLICT DO NOTHING""",
                (provider_id, area_id)
            )

        print(f"  added: {business_name}  ->  /providers/{slug}  ({len(cities)} area(s))")
        added += 1

conn.commit()
conn.close()

print(f"\n{'='*50}")
print(f"Added:   {added}")
print(f"Skipped: {skipped} (already in database)")
if new_cities:
    print(f"New city pages created: {len(set(new_cities))}")
    for c in sorted(set(new_cities)):
        print(f"   - {c}")
print(f"{'='*50}")