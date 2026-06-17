import sqlite3

connection = sqlite3.connect("app.db")
cursor = connection.cursor()

cursor.execute("""
    CREATE TABLE IF NOT EXISTS users (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        email TEXT UNIQUE NOT NULL,
        password_hash TEXT NOT NULL,
        role TEXT NOT NULL DEFAULT 'owner',
        created_at TEXT NOT NULL
        )
    """)

cursor.execute("""
    CREATE TABLE IF NOT EXISTS services (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        slug TEXT UNIQUE NOT NULL,
        name TEXT NOT NULL
        )
    """)

cursor.execute(
    "INSERT OR IGNORE INTO services (slug, name) VALUES (?, ?)",
    ("rv-inspection", "RV Inspection")
)

cursor.execute("""
    CREATE TABLE IF NOT EXISTS providers (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        user_id INTEGER,
        business_name TEXT NOT NULL,
        slug TEXT UNIQUE NOT NULL,
        bio TEXT,
        home_lat REAL,
        home_lng REAL,
        service_radius_mi INTEGER,
        insurance_verified INTEGER DEFAULT 0,
        claimed INTEGER DEFAULT 0,
        status TEXT DEFAULT 'live',
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
        id INTEGER PRIMARY KEY AUTOINCREMENT,
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
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        state TEXT NOT NULL,
        state_slug TEXT NOT NULL,   -- 'texas'
        city TEXT NOT NULL,
        city_slug TEXT NOT NULL,    -- 'austin'
        UNIQUE (state_slug, city_slug)
    )
""")

# --- PROVIDER_AREAS: many-to-many. Which providers serve which areas ---
cursor.execute("""
    CREATE TABLE IF NOT EXISTS provider_areas (
        provider_id INTEGER NOT NULL,
        service_area_id INTEGER NOT NULL,
        PRIMARY KEY (provider_id, service_area_id),
        FOREIGN KEY (provider_id) REFERENCES providers(id),
        FOREIGN KEY (service_area_id) REFERENCES service_areas(id)
    )
""")

# --- LEADS: an owner requests a service (Phase 4) ---
cursor.execute("""
    CREATE TABLE IF NOT EXISTS leads (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        owner_id INTEGER,
        provider_id INTEGER NOT NULL,
        service_id INTEGER NOT NULL,
        message TEXT,
        status TEXT DEFAULT 'new',   -- 'new' | 'responded' | 'closed'
        created_at TEXT NOT NULL,
        FOREIGN KEY (owner_id) REFERENCES users(id),
        FOREIGN KEY (provider_id) REFERENCES providers(id),
        FOREIGN KEY (service_id) REFERENCES services(id)
    )
""")

# --- BOOKINGS: a paid, scheduled job (Phase 5, Stripe) ---
cursor.execute("""
    CREATE TABLE IF NOT EXISTS bookings (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        owner_id INTEGER NOT NULL,
        provider_id INTEGER NOT NULL,
        service_id INTEGER NOT NULL,
        status TEXT DEFAULT 'requested',
        price REAL,
        stripe_pi TEXT,              -- Stripe payment intent id
        scheduled_for TEXT,
        created_at TEXT NOT NULL,
        FOREIGN KEY (owner_id) REFERENCES users(id),
        FOREIGN KEY (provider_id) REFERENCES providers(id),
        FOREIGN KEY (service_id) REFERENCES services(id)
    )
""")

# --- REVIEWS: tied to a real booking, so they're credible (Phase 6) ---
cursor.execute("""
    CREATE TABLE IF NOT EXISTS reviews (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        booking_id INTEGER NOT NULL,
        provider_id INTEGER NOT NULL,
        rating INTEGER NOT NULL,
        body TEXT,
        created_at TEXT NOT NULL,
        FOREIGN KEY (booking_id) REFERENCES bookings(id),
        FOREIGN KEY (provider_id) REFERENCES providers(id)
    )
""")

# --- PROVIDER_TRAVEL: time-bounded availability that surfaces a provider on an
#     EXISTING city page's live roster. Never creates/removes pages. ---
cursor.execute("""
    CREATE TABLE IF NOT EXISTS provider_travel (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        provider_id INTEGER NOT NULL,
        service_area_id INTEGER NOT NULL,
        start_date TEXT NOT NULL,
        end_date TEXT NOT NULL,
        created_at TEXT NOT NULL,
        FOREIGN KEY (provider_id) REFERENCES providers(id),
        FOREIGN KEY (service_area_id) REFERENCES service_areas(id)
    )
""")

connection.commit()
connection.close()
print("Schema ready: app.db created with all Phase 1 tables + 'rv-inspection' seeded.")