import sqlite3

connection = sqlite3.connect("microsub.db")

with connection:
    cursor = connection.cursor()

    cursor.execute("""CREATE TABLE IF NOT EXISTS following(
        channel text,
        url text,
        etag text,
        photo text,
        name text,
        id integer primary key autoincrement,
        muted integer,
        blocked integer
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
        hidden integer,
        feed_id integer,
        id integer primary key not null
    )
    """)

    cursor.execute("""CREATE TABLE IF NOT EXISTS websub_subscriptions(
        url text,
        uid text,
        channel text,
        approved integer
    """)

    print("microsub.db has been seeded.")
    print("You are now ready to run the Microsub server.")