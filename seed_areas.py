import sqlite3, re

def slugify(text):
    text = text.lower().strip()
    text = re.sub(r"[^a-z0-9]+", "-", text)
    text = re.sub(r"-+", "-", text)
    return text.strip("-")

connection = sqlite3.connect("app.db")
cursor = connection.cursor()
cursor.execute("DELETE FROM service_areas")

florida_cities = [
    "Tampa", "Orlando", "Jacksonville", "Fort Myers", "Sarasota",
    "Ocala", "Tallahassee", "Pensacola", "Fort Lauderdale", "Daytona Beach",
    "Lakeland", "Gainesville", "St. Petersburg", "Naples", "Kissimmee", "Clearwater"
]

for city in florida_cities:
    cursor.execute(
        "INSERT OR IGNORE INTO service_areas (state, state_slug, city, city_slug) VALUES (?, ?, ?, ?)",
        ("Florida", "florida", city, slugify(city))
    )

connection.commit()
connection.close()
print(f"Seeded {len(florida_cities)} Florida service areas.")