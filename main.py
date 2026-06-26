from flask import Flask, render_template, request, abort, redirect, url_for, session, Response
from werkzeug.security import generate_password_hash, check_password_hash
from datetime import date
from functools import wraps
import os
import psycopg2
import re
from psycopg2.extras import RealDictCursor

app = Flask(__name__)
app.secret_key = os.environ.get('SECRET_KEY', 'dev-secret-change-in-prod')

DATABASE_URL = os.environ.get('DATABASE_URL', '')
if DATABASE_URL.startswith('postgres://'):
    DATABASE_URL = DATABASE_URL.replace('postgres://', 'postgresql://', 1)

def query_db(query, args=()):
    conn = psycopg2.connect(DATABASE_URL)
    cursor = conn.cursor(cursor_factory=RealDictCursor)
    cursor.execute(query, args)
    rows = cursor.fetchall()
    conn.close()
    return rows

def execute_db(query, args=()):
    conn = psycopg2.connect(DATABASE_URL)
    cursor = conn.cursor()
    cursor.execute(query, args)
    try:
        result = cursor.fetchone()
        new_id = result[0] if result else None
    except Exception:
        new_id = None
    conn.commit()
    conn.close()
    return new_id

def current_user():
    user_id = session.get('user_id')
    if not user_id:
        return None
    rows = query_db("SELECT id, email, role FROM users WHERE id = %s", (user_id,))
    return rows[0] if rows else None

@app.context_processor
def inject_user():
    return {'current_user': current_user()}

def login_required(f):
    @wraps(f)
    def decorated(*args, **kwargs):
        if not current_user():
            return redirect(url_for('login'))
        return f(*args, **kwargs)
    return decorated

def provider_required(f):
    @wraps(f)
    def decorated(*args, **kwargs):
        user = current_user()
        if not user or user['role'] not in ('provider', 'admin'):
             return redirect(url_for('login'))
        return f(*args, **kwargs)
    return decorated

def slugify(text):
    text = text.lower().strip()
    text = re.sub(r"[^a-z0-9]+", "-", text)
    text = re.sub(r"-+", "-", text)
    return text.strip("-")

def get_service_or_404(service_slug):
    rows = query_db("SELECT id, slug, name FROM services WHERE slug = %s", (service_slug,))
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
        "SELECT city, city_slug, state FROM service_areas WHERE state_slug = %s ORDER BY city",
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
        """
        SELECT id, city, state, state_slug, city_slug 
        FROM service_areas 
        WHERE state_slug = %s AND city_slug = %s
        """,
        (state_slug, city_slug)
    )

    
    if not areas:
        abort(404)   # no service_area row = no page. The churn rule, enforced.
    area = areas[0]
    today = date.today().isoformat()

    providers = query_db(
        """
        SELECT DISTINCT ON (slug) business_name, slug, bio, coverage_type, travel_end_date
        FROM (
            SELECT providers.business_name, providers.slug, providers.bio, 'home' AS coverage_type, NULL AS travel_end_date, 1 AS priority
            FROM providers
            JOIN provider_areas ON provider_areas.provider_id = providers.id
            JOIN services ON services.id = provider_services.service_id
            WHERE provider_areas.service_area_id = %s AND services.slug = %s AND providers.status = 'live'
            UNION ALL
            SELECT providers.business_name, providers.slug, providers.bio, 'traveling' AS coverage_type, provider_travel.end_date AS travel_end_date, 2 AS priority
            FROM providers
            JOIN provider_travel ON provider_travel.provider_id = providers.id
            JOIN provider_services ON provider_services.provider_id = providers.id
            JOIN services ON services.id = provider_services.service_id
            WHERE provider_travel.service_area_id = %s AND services.slug = %s AND providers.status = 'live' AND provider_travel.start_date <= %s AND provider_travel.end_date >= %s
        ) combined
        ORDER BY slug, priority
        """,
        (area['id'], service_slug, area['id'], service_slug, today, today)
    )

    return render_template('city.html', service=service, area=area, providers=providers)





@app.route('/providers/<slug>')
def provider_profile(slug):
    rows = query_db("SELECT * FROM providers WHERE slug = %s AND status = 'live'", (slug,))
    if not rows:
        abort(404)
    provider = rows[0]
    pid = provider['id']

    services = query_db("""
        SELECT services.name, services.slug, provider_services.price_from, provider_services.price_to
        FROM provider_services JOIN services ON services.id = provider_services.service_id
        WHERE provider_services.provider_id = %s ORDER BY services.name""", (pid,))

    areas = query_db("""
        SELECT service_areas.city, service_areas.state_slug, service_areas.city_slug
        FROM provider_areas JOIN service_areas ON service_areas.id = provider_areas.service_area_id
        WHERE provider_areas.provider_id = %s ORDER BY service_areas.city""", (pid,))

    credentials = query_db(
        "SELECT body, level, verified_at FROM credentials WHERE provider_id = %s ORDER BY body", (pid,))

    reviews = query_db(
        "SELECT rating, body, created_at FROM reviews WHERE provider_id = %s ORDER BY created_at DESC", (pid,))
    stats = query_db(
        "SELECT AVG(rating) AS avg_rating, COUNT(*) AS review_count FROM reviews WHERE provider_id = %s", (pid,))[0]

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
            pages.append(url_for('service_state', service_slug=s['slug'], state_slug=st['state_slug'], _external=True))
        for area in query_db("SELECT state_slug, city_slug FROM service_areas"):
            pages.append(url_for('service_city', service_slug=s['slug'], state_slug=area['state_slug'], city_slug=area['city_slug'], _external=True))
    for p in query_db("SELECT slug FROM providers WHERE status = 'live'"):
        pages.append(url_for('provider_profile', slug=p['slug'], _external=True))
            
    xml = ['<?xml version="1.0" encoding="UTF-8"?>', '<urlset xmlns="http://www.sitemaps.org/schemas/sitemap/0.9">']
    for url in pages:
        xml.append(f"<url><loc>{url}</loc></url>")
    
    xml.append("</urlset>")
    
    return Response("\n".join(xml), mimetype="application/xml")

@app.route('/register', methods=['GET', 'POST'])
def register():
    if request.method == 'POST':
        email = request.form.get('email', '').strip().lower()
        password = request.form.get('password', '')
        role = request.form.get('role', 'owner')

        errors = []
        if not email:
            errors.append("Email is required.")
        if len(password) < 8:
            errors.append("Password must be at least 8 characters.")
        if query_db("SELECT id FROM users WHERE email = %s", (email,)):
            errors.append("An account with that email already exists.")

        if errors:
            return render_template('register.html', errors=errors, email=email)

        user_id = execute_db(
            "INSERT INTO users (email, password_hash, role, created_at) VALUES (%s, %s, %s, %s) RETURNING id",
            (email, generate_password_hash(password), role, date.today().isoformat())
        )
        session['user_id'] = user_id
        return redirect(url_for('home'))

    return render_template('register.html', errors=None, email='')


@app.route('/login', methods=['GET', 'POST'])
def login():
    if request.method == 'POST':
        email = request.form.get('email', '').strip().lower()
        password = request.form.get('password', '')

        rows = query_db("SELECT id, password_hash FROM users WHERE email = %s", (email,))
        if rows and check_password_hash(rows[0]['password_hash'], password):
            session['user_id'] = rows[0]['id']
            return redirect(url_for('home'))

        return render_template('login.html', error="Incorrect email or password.", email=email)

    return render_template('login.html', error=None, email='')


@app.route('/logout')
def logout():
    session.clear()
    return redirect(url_for('home'))


@app.route('/dashboard')
@login_required
def dashboard():
    user = current_user()
    provider = query_db(
        "SELECT * FROM providers WHERE owner_user_id = %s", (user['id'],)
    )
    provider = provider[0] if provider else None
    return render_template('dashboard.html', user=user, provider=provider)


@app.route('/claim', methods=['GET', 'POST'])
@login_required
def claim():
    user = current_user()
    if user['role'] != 'provider':
        return redirect(url_for('dashboard'))
    existing = query_db("SELECT id FROM providers WHERE owner_user_id = %s", (user['id'],))
    if existing:
        return redirect(url_for('dashboard'))
    results = []
    search = ''
    if request.method == 'POST':
        search = request.form.get('search', '').strip()
        if search:
            results = query_db(
                """SELECT id, business_name, home_city, home_state, claimed FROM providers WHERE business_name ILIKE %s AND owner_user_id IS NULL ORDER BY business_name
                """,
                (f"%{search}%",)
            )
    return render_template('claim.html', search=search, results=results)


@app.route('/claim/<int:provider_id>', methods=['POST'])
@login_required
def claim_profile(provider_id):
    user = current_user()
    if user['role'] != 'provider':
        return redirect(url_for('dashboard'))
    rows = query_db(
        "SELECT id, owner_user_id FROM providers WHERE id = %s", (provider_id,)
    )
    if not rows or rows[0]['owner_user_id'] is not None:
        return redirect(url_for('claim'))

    execute_db(
        """
        UPDATE providers
        SET owner_user_id = %s, claimed = 1
        WHERE id = %s
        """, (user['id'], provider_id)
    )
    return redirect(url_for('dashboard'))


@app.route('/dashboard/edit', methods=['GET', 'POST'])
@login_required
def dashboard_edit():
    user = current_user()
    rows = query_db("SELECT * FROM providers WHERE owner_user_id = %s", (user['id'],))
    if not rows:
        return redirect(url_for('dashboard'))
    provider = rows[0]
    if request.method == 'POST':
        business_name = request.form.get('business_name', '').strip()
        contact_name = request.form.get('contact_name', '').strip()
        bio = request.form.get('bio', '').strip()
        phone = request.form.get('phone', '').strip()
        website = request.form.get('website', '').strip()
        home_city = request.form.get('home_city', '').strip()
        home_state = request.form.get('home_state', '').strip()
        radius = request.form.get('service_radius_mi', '50').strip()
        
        errors = []
        if not business_name:
            errors.append("Business name is required.")
        if not home_city:
            errors.append("City is required.")

        if errors:
            return render_template('dashboard_edit.html', provider=provider, errors=errors)

        execute_db(
            """
            UPDATE providers SET business_name = %s, contact_name = %s, bio = %s, phone = %s, website = %s, home_city = %s, home_state = %s, service_radius_mi = %s
            WHERE owner_user_id = %s
            """,
            (business_name, contact_name, bio, phone, website, home_city, home_state, radius, user['id'])
        )
        return redirect(url_for('dashboard'))
    return render_template('dashboard_edit.html', provider=provider, errors=None)


@app.route('/dashboard/travel', methods=['GET', 'POST'])
@login_required
def dashboard_travel():
    user = current_user()
    rows = query_db("SELECT * FROM providers WHERE owner_user_id = %s", (user['id'],))
    if not rows:
        return redirect(url_for('dashboard'))
    provider = rows[0]
    errors = None

    if request.method == 'POST':
        service_area_id = request.form.get('service_area_id', '').strip()
        start_date = request.form.get('start_date', '').strip()
        end_date = request.form.get('end_date', '').strip()

        errors = []
        if not service_area_id:
            errors.append("Please select a city")
        if not start_date:
            errors.append("Start date is required")
        if not end_date:
            errors.append("End date is required")
        if start_date and end_date and end_date < start_date:
            errors.append("End date must be after start date")

        if not errors:
            execute_db(
                """
                INSERT INTO provider_travel (provider_id, service_area_id, start_date, end_date, created_at)
                VALUES (%s, %s, %s, %s, %s)
                """,
                (provider['id'], service_area_id, start_date, end_date, date.today().isoformat())
            )
            return redirect(url_for('dashboard_travel'))
    
    areas = query_db("SELECT id, city, state FROM service_areas ORDER BY state, city")

    travel_dates = query_db(
        """
        SELECT provider_travel.id, service_areas.city, service_areas.state, provider_travel.start_date, provider_travel.end_date
        FROM provider_travel
        JOIN service_areas ON service_areas.id = provider_travel.service_area_id
        WHERE provider_travel.provider_id = %s
        ORDER BY provider_travel.start_date DESC
        """,
        (provider['id'],)
    )
    return render_template('dashboard_travel.html', provider=provider, areas=areas, travel_dates=travel_dates, errors=errors, today=date.today().isoformat())


@app.route('/dashboard/travel/<int:travel_id>/delete', methods=['POST'])
@login_required
def delete_travel(travel_id):
    user = current_user()
    rows = query_db("SELECT id FROM providers WHERE owner_user_id = %s", (user['id'],))
    if not rows:
        return redirect(url_for('dashboard'))
    execute_db(
        "DELETE FROM provider_travel WHERE id = %s AND provider_id = %s",
        (travel_id, rows[0]['id'])
    )
    return redirect(url_for('dashboard_travel'))


@app.route('/providers/<slug>/request', methods=['POST'])
def request_service(slug):
    rows = query_db("SELECT id, business_name FROM providers WHERE slug = %s AND status = 'live'", (slug,))
    if not rows:
        abort(404)
    provider = rows[0]

    owner_name = request.form.get('owner_name', '').strip()
    owner_email = request.form.get('owner_email', '').strip()
    owner_phone = request.form.get('owner_phone', '').strip()
    rv_details = request.form.get('rv_details', '').strip()
    preferred_date = request.form.get('preferred_date', '').strip()
    message = request.form.get('message', '').strip()

    errors = []
    if not owner_name:
        errors.append("Name is required.")
    if not owner_email:
        errors.append("Email is required.")

    if errors:
        return render_template('request_sent.html', provider=provider, slug=slug, errors=errors, success=False)

    service = query_db("SELECT id FROM services WHERE slug = 'rv-inspection'")
    service_id = service[0]['id'] if service else None
    user = current_user()
    owner_id = user['id'] if user else None

    execute_db(
        """
        INSERT INTO leads (owner_id, provider_id, service_id, message, status, created_at, owner_name, owner_email, owner_phone, rv_details, preferred_date)
        VALUES (%s, %s, %s, %s, 'new', %s, %s, %s, %s, %s, %s)
        """,
        (owner_id, provider['id'], service_id, message, date.today().isoformat(), owner_name, owner_email, owner_phone, rv_details, preferred_date)
    )
    return render_template('request_sent.html', provider=provider, slug=slug, errors=None, success=True)

@app.route('/dashboard/leads')
@login_required
def dashboard_leads():
    user = current_user()
    rows = query_db("SELECT id, business_name FROM providers WHERE owner_user_id = %s", (user['id'],))
    if not rows:
        return redirect(url_for('dashboard'))
    provider = rows[0]
    leads = query_db(
        """
        SELECT owner_name, owner_email, owner_phone, rv_details, preferred_date, message, status, created_at
        FROM leads
        WHERE provider_id = %s
        ORDER BY created_at DESC
        """,
        (provider['id'],)
    )

    return render_template('dashboard_leads.html', provider=provider, leads=leads)


        
if __name__ == '__main__':
    app.run(host='0.0.0.0', port=5000, debug=False)