import os
import psycopg2

DATABASE_URL = os.environ.get('DATABASE_URL', '')
if DATABASE_URL.startswith('postgres://'):
    DATABASE_URL = DATABASE_URL.replace('postgres://', 'postgresql://', 1)

conn = psycopg2.connect(DATABASE_URL)
cursor = conn.cursor()

cursor.execute("""
    CREATE TABLE IF NOT EXISTS users (
        id SERIAL PRIMARY KEY,
        email TEXT UNIQUE NOT NULL,
        password_hash TEXT NOT NULL,
        role TEXT NOT NULL DEFAULT 'owner',
        created_at TEXT NOT NULL
    )
""")

cursor.execute("""
    CREATE TABLE IF NOT EXISTS services (
        id SERIAL PRIMARY KEY,
        slug TEXT UNIQUE NOT NULL,
        name TEXT NOT NULL
    )
""")

cursor.execute("""
    INSERT INTO services (slug, name) VALUES ('rv-inspection', 'RV Inspection')
    ON CONFLICT DO NOTHING
""")

cursor.execute("""
    CREATE TABLE IF NOT EXISTS providers (
        id SERIAL PRIMARY KEY,
        user_id INTEGER,
        business_name TEXT NOT NULL,
        slug TEXT UNIQUE NOT NULL,
        bio TEXT,
        contact_name TEXT,
        home_city TEXT,
        home_state TEXT,
        home_lat REAL,
        home_lng REAL,
        service_radius_mi INTEGER,
        insurance_verified INTEGER DEFAULT 0,
        claimed INTEGER DEFAULT 0,
        status TEXT DEFAULT 'live',
        owner_user_id INTEGER,
        created_at TEXT NOT NULL,
        FOREIGN KEY (user_id) REFERENCES users(id)
    )
""")

cursor.execute("""
    CREATE TABLE IF NOT EXISTS provider_services (
        provider_id INTEGER NOT NULL,
        service_id INTEGER NOT NULL,
        price_from REAL,
        price_to REAL,
        PRIMARY KEY (provider_id, service_id),
        FOREIGN KEY (provider_id) REFERENCES providers(id),
        FOREIGN KEY (service_id) REFERENCES services(id)
    )
""")

cursor.execute("""
    CREATE TABLE IF NOT EXISTS credentials (
        id SERIAL PRIMARY KEY,
        provider_id INTEGER NOT NULL,
        body TEXT NOT NULL,
        level TEXT,
        verified_at TEXT,
        source TEXT,
        FOREIGN KEY (provider_id) REFERENCES providers(id)
    )
""")

cursor.execute("""
    CREATE TABLE IF NOT EXISTS service_areas (
        id SERIAL PRIMARY KEY,
        state TEXT NOT NULL,
        state_slug TEXT NOT NULL,
        city TEXT NOT NULL,
        city_slug TEXT NOT NULL,
        UNIQUE (state_slug, city_slug)
    )
""")

cursor.execute("""
    CREATE TABLE IF NOT EXISTS provider_areas (
        provider_id INTEGER NOT NULL,
        service_area_id INTEGER NOT NULL,
        PRIMARY KEY (provider_id, service_area_id),
        FOREIGN KEY (provider_id) REFERENCES providers(id),
        FOREIGN KEY (service_area_id) REFERENCES service_areas(id)
    )
""")

cursor.execute("""
    CREATE TABLE IF NOT EXISTS provider_travel (
        id SERIAL PRIMARY KEY,
        provider_id INTEGER NOT NULL,
        service_area_id INTEGER NOT NULL,
        start_date TEXT NOT NULL,
        end_date TEXT NOT NULL,
        created_at TEXT NOT NULL,
        FOREIGN KEY (provider_id) REFERENCES providers(id),
        FOREIGN KEY (service_area_id) REFERENCES service_areas(id)
    )
""")

cursor.execute("""
    CREATE TABLE IF NOT EXISTS leads (
        id SERIAL PRIMARY KEY,
        owner_id INTEGER,
        provider_id INTEGER NOT NULL,
        service_id INTEGER NOT NULL,
        message TEXT,
        status TEXT DEFAULT 'new',
        created_at TEXT NOT NULL,
        FOREIGN KEY (owner_id) REFERENCES users(id),
        FOREIGN KEY (provider_id) REFERENCES providers(id),
        FOREIGN KEY (service_id) REFERENCES services(id)
    )
""")

cursor.execute("""
    CREATE TABLE IF NOT EXISTS bookings (
        id SERIAL PRIMARY KEY,
        owner_id INTEGER NOT NULL,
        provider_id INTEGER NOT NULL,
        service_id INTEGER NOT NULL,
        status TEXT DEFAULT 'requested',
        price REAL,
        stripe_pi TEXT,
        scheduled_for TEXT,
        created_at TEXT NOT NULL,
        FOREIGN KEY (owner_id) REFERENCES users(id),
        FOREIGN KEY (provider_id) REFERENCES providers(id),
        FOREIGN KEY (service_id) REFERENCES services(id)
    )
""")

cursor.execute("""
    CREATE TABLE IF NOT EXISTS reviews (
        id SERIAL PRIMARY KEY,
        booking_id INTEGER NOT NULL,
        provider_id INTEGER NOT NULL,
        rating INTEGER NOT NULL,
        body TEXT,
        created_at TEXT NOT NULL,
        FOREIGN KEY (booking_id) REFERENCES bookings(id),
        FOREIGN KEY (provider_id) REFERENCES providers(id)
    )
""")

conn.commit()
conn.close()
print("PostgreSQL schema ready.")