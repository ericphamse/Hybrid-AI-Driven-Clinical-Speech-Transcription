import sqlite3

# connect to your .db file
conn = sqlite3.connect("clinical_transcription.db")
cursor = conn.cursor()

# get all table names
cursor.execute("SELECT name FROM sqlite_master WHERE type='table';")
tables = cursor.fetchall()

for table_name in tables:
    table_name = table_name[0]  # unpack tuple
    print(f"\n📌 Table: {table_name}")
    print("-" * (len(table_name) + 8))

    # get all rows
    cursor.execute(f"SELECT * FROM {table_name}")
    rows = cursor.fetchall()

    # get column names
    col_names = [description[0] for description in cursor.description]
    print(" | ".join(col_names))  # header row

    for row in rows:
        print(row)

conn.close()
