from flask import Flask, render_template, abort, Response, url_for
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

@app.route('/providers/<slug>')
def provider_profile(slug):
    rows = query_db("SELECT * FROM providers WHERE slug = ? AND status = 'live'", (slug,))
    if not rows:
        abort(404)
    provider = rows[0]
    pid = provider['id']

    services = query_db("""
        SELECT services.name, services.slug, provider_services.price_from, provider_services.price_to
        FROM provider_services JOIN services ON services.id = provider_services.service_id
        WHERE provider_services.provider_id = ? ORDER BY services.name""", (pid,))

    areas = query_db("""
        SELECT service_areas.city, service_areas.state_slug, service_areas.city_slug
        FROM provider_areas JOIN service_areas ON service_areas.id = provider_areas.service_area_id
        WHERE provider_areas.provider_id = ? ORDER BY service_areas.city""", (pid,))

    credentials = query_db(
        "SELECT body, level, verified_at FROM credentials WHERE provider_id = ? ORDER BY body", (pid,))

    reviews = query_db(
        "SELECT rating, body, created_at FROM reviews WHERE provider_id = ? ORDER BY created_at DESC", (pid,))
    stats = query_db(
        "SELECT AVG(rating) AS avg_rating, COUNT(*) AS review_count FROM reviews WHERE provider_id = ?", (pid,))[0]

    cred_names = " and ".join(f"{c['body']} {c['level']}" for c in credentials) if credentials else ""
    meta_desc = f"{provider['contact_name']} — {provider['business_name']}"
    if cred_names:
        meta_desc += f", {cred_names}"
    meta_desc += f", serving {provider['home_city']}, {provider['home_state']} and within {provider['service_radius_mi']} miles."

    return render_template('provider.html', provider=provider, services=services, areas=areas,
                           credentials=credentials, reviews=reviews,
                           avg_rating=stats['avg_rating'], review_count=stats['review_count'],
                           meta_desc=meta_desc)

@app.route('/robots.txt')
def robots():
    lines = [
        "User-agent: *",
        "Allow: /",
        f"Sitemap: {url_for('sitemap', _external=True)}",
    ]
    return Response("\n".join(lines), mimetype="text/plain")


@app.route('/sitemap.xml')
def sitemap():
    pages = []

    pages.append(url_for('home', _external=True))
    for s in query_db("SELECT slug FROM services"):
        pages.append(url_for('service_pillar', service_slug=s['slug'], _external=True))
    services = query_db("SELECT slug FROM services")
    states = query_db("SELECT DISTINCT state_slug FROM service_areas")
    for s in services:
        for st in states:
            pages.append(url_for('service_state', service_slug=s['slug'], _external=True))
        for area in query_db("SELECT state_slug, city_slug FROM service_areas"):
            pages.append(url_for('service_city', service_slug=s['slug'], state_slug=area['state_slug'], city_slug=area['city_slug'], _external=True))
        for p in query_db("SELECT slug FROM providers WHERE status = 'live'"):
            pages.append(url_for('provider_profile', slug=p['slug'], _external=True))
            
    xml = ['<?xml version="1.0" encoding="UTF-8"?>', '<urlset xmlns="http://www.sitemaps.org/schemas/sitemap/0.9">']
    for url in pages:
        xml.append(f"<url><loc>{url}</loc></url>")
    
    xml.append("</urlset>")
    
    return Response("\n".join(xml), mimetype="application/xml")



if __name__ == '__main__':
    app.run(host='0.0.0.0', port=5000)