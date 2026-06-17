from flask import Flask, render_template, abort
import sys
import pysqlite3
sys.modules["sqlite3"] = pysqlite3
import sqlite3
import re

app = Flask(__name__)

def query_db(query, args=()):
    connection = sqlite3.connect("app.db")
    connection.row_factory = sqlite3.Row
    cursor = connection.cursor()
    cursor.execute(query, args)
    rows = cursor.fetchall()
    connection.close()
    return rows

def slugify(text):
    text = text.lower().strip()
    text = re.sub(r"[^a-z0-9]+", "-", text)
    text = re.sub(r"-+", "-", text)
    return text.strip("-")

def get_service_or_404(service_slug):
    rows = query_db("SELECT id, slug, name FROM services WHERE slug = ?", (service_slug,))
    if not rows:
        abort(404)
    return rows[0]

@app.route('/')
def home():
    services = query_db("SELECT slug, name FROM services ORDER BY name")
    return render_template('home.html', services=services)

@app.route('/<service_slug>')
def service_pillar(service_slug):
    service = get_service_or_404(service_slug)
    states = query_db(
        "SELECT DISTINCT state, state_slug FROM service_areas ORDER BY state"
    )
    return render_template('pillar.html', service=service, states=states)

@app.route('/<service_slug>/<state_slug>')
def service_state(service_slug, state_slug):
    service = get_service_or_404(service_slug)
    cities = query_db(
        "SELECT city, city_slug, state FROM service_areas WHERE state_slug = ? ORDER BY city",
        (state_slug,)
    )
    if not cities:
        abort(404)
    return render_template('state.html', service=service,
                           state_name=cities[0]['state'], state_slug=state_slug, cities=cities)

@app.route('/<service_slug>/<state_slug>/<city_slug>')
def service_city(service_slug, state_slug, city_slug):
    service = get_service_or_404(service_slug)

    areas = query_db(
        "SELECT id, city, state, state_slug, city_slug FROM service_areas WHERE state_slug = ? AND city_slug = ?",
        (state_slug, city_slug)
    )
    if not areas:
        abort(404)   # no service_area row = no page. The churn rule, enforced.
    area = areas[0]

    providers = query_db(
        """
        SELECT DISTINCT providers.business_name, providers.slug, providers.bio
        FROM providers
        JOIN provider_areas ON provider_areas.provider_id = providers.id
        JOIN provider_services ON provider_services.provider_id = providers.id
        JOIN services ON services.id = provider_services.service_id
        WHERE provider_areas.service_area_id = ?
          AND services.slug = ?
          AND providers.status = 'live'
        ORDER BY providers.business_name
        """,
        (area['id'], service_slug)
    )

    return render_template('city.html', service=service, area=area, providers=providers)

if __name__ == '__main__':
    app.run(host='0.0.0.0', port=5000)