import sqlite3

conn = sqlite3.connect("database/vision_db.sqlite")
cursor = conn.cursor()

cursor.execute("DELETE FROM attendance_logs;")

conn.commit()
conn.close()

print("Table cleared successfully ✅")