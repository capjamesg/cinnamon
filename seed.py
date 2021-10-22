import sqlite3

connection = sqlite3.connect("microsub.db")

with connection:
    cursor = connection.cursor()

    cursor.execute("""CREATE TABLE IF NOT EXISTS following(
        channel text,
        url text,
        etag text
    )
    """)

    cursor.execute("""CREATE TABLE IF NOT EXISTS channels(
        channel text,
        uid text,
        position text
    )
    """)

    cursor.execute("""CREATE TABLE IF NOT EXISTS timeline(
        channel text,
        jf2 text,
        date integer,
        read_status text,
        url text,
        uid text,
        hidden integer
    )
    """)

    cursor.execute("""CREATE TABLE IF NOT EXISTS websub_subscriptions(
        url text,
        uid text
    """)

    print("microsub.db has been seeded.")
    print("You are now ready to run the Microsub server.")