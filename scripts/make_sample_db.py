"""Generate a small sample Chinook-like SQLite DB for local testing."""

import sqlite3
from pathlib import Path

DB_PATH = Path(__file__).resolve().parent.parent / "chinook.db"


def main() -> None:
    if DB_PATH.exists():
        DB_PATH.unlink()
    conn = sqlite3.connect(str(DB_PATH))
    conn.executescript(
        """
        CREATE TABLE artist (
            artist_id INTEGER PRIMARY KEY,
            name TEXT NOT NULL
        );
        CREATE TABLE album (
            album_id INTEGER PRIMARY KEY,
            title TEXT NOT NULL,
            artist_id INTEGER NOT NULL,
            FOREIGN KEY (artist_id) REFERENCES artist(artist_id)
        );
        CREATE TABLE track (
            track_id INTEGER PRIMARY KEY,
            name TEXT NOT NULL,
            album_id INTEGER,
            unit_price REAL NOT NULL,
            email TEXT
        );
        CREATE TABLE invoice (
            invoice_id INTEGER PRIMARY KEY,
            customer_id INTEGER NOT NULL,
            invoice_date TEXT NOT NULL,
            total REAL NOT NULL
        );
        INSERT INTO artist VALUES
            (1, 'Artist One'), (2, 'Artist Two'), (3, 'Artist Three');
        INSERT INTO album VALUES
            (1, 'Album A', 1), (2, 'Album B', 2), (3, 'Album C', 3);
        INSERT INTO track VALUES
            (1, 'Song 1', 1, 0.99, 'a@example.com'),
            (2, 'Song 2', 1, 1.49, 'b@example.com'),
            (3, 'Song 3', 2, 0.89, 'c@example.com'),
            (4, 'Song 4', 3, 1.29, NULL);
        INSERT INTO invoice VALUES
            (1, 10, '2024-01-15', 42.50),
            (2, 11, '2024-02-20', 15.00);
        """
    )
    conn.commit()
    conn.close()
    print(f"Created sample DB at {DB_PATH}")


if __name__ == "__main__":
    main()
