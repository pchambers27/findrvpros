import psycopg2
import os

DATABASE_URL = os.environ.get('DATABASE_URL', '')
if DATABASE_URL.startswith('postgres://'):
     DATABASE_URL = DATABASE_URL.replace('postgres://', 'postgresql://', 1)

conn = psycopg2.connect(DATABASE_URL)
cursor = conn.cursor()

new_columns = {
    'owner_name': 'TEXT',
    'owner_email': 'TEXT',
    'owner_phone': 'TEXT',
    'rv_details': 'TEXT',
    'preferred_date': 'TEXT',
}

for col, coltype in new_columns.items():
    cursor.execute(
        """
        SELECT column_name FROM information_schema.columns
        WHERE table_name = 'leads' AND column_name = %s
        """,
        (col,)
    )
    if not cursor.fetchone():
         cursor.execute(f"ALTER TABLE leads ADD COLUMN {col} {coltype}")
         print(f"Added column: {col}")

    else:
         print(f"Already exists: {col}")

conn.commit()
conn.close()
print("Migration complete.")