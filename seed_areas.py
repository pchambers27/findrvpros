import os, psycopg2, re
from psycopg2.extras import RealDictCursor

def slugify(text):
    text = text.lower().strip()
    text = re.sub(r"[^a-z0-9]+", "-", text)
    text = re.sub(r"-+", "-", text)
    return text.strip("-")

DATABASE_URL = os.environ.get('DATABASE_URL', '')
if DATABASE_URL.startswith('postgres://'):
    DATABASE_URL = DATABASE_URL.replace('postgres://', 'postgresql://', 1)

connection = psycopg2.connect(DATABASE_URL)
cursor = connection.cursor(cursor_factory=RealDictCursor)
cursor.execute("DELETE FROM service_areas")

florida_cities = [
    "Tampa", "Orlando", "Jacksonville", "Fort Myers", "Sarasota",
    "Ocala", "Tallahassee", "Pensacola", "Fort Lauderdale", "Daytona Beach",
    "Lakeland", "Gainesville", "St. Petersburg", "Naples", "Kissimmee", "Clearwater"
]

for city in florida_cities:
    cursor.execute(
        "INSERT INTO service_areas (state, state_slug, city, city_slug) VALUES (%s, %s, %s, %s) ON CONFLICT DO NOTHING",
        ("Florida", "florida", city, slugify(city))
    )

connection.commit()
connection.close()
print(f"Seeded {len(florida_cities)} Florida service areas.")
