import sqlite3

from errors import *
from tyre import Tyre, TyreSet


class TyreDatabase:
    def __init__(self, db_path):
        self.db_path = db_path
        self.con = sqlite3.connect(self.db_path)
        self.con.row_factory = sqlite3.Row
        self.PAGE_SIZE = 100
        self.cursor = self.con.cursor()

        self.cursor.execute("PRAGMA foreign_keys = ON;")
        self.cursor.execute("PRAGMA journal_mode=WAL;")

        with self.con:
            self.con.execute(
                """
                CREATE TABLE IF NOT EXISTS users (
                    id TEXT PRIMARY KEY NOT NULL,
                    username TEXT NOT NULL UNIQUE,
                    email TEXT NOT NULL UNIQUE,
                    password_hash TEXT NOT NULL,
                    created_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP
                )
                """
            )
            self.con.execute(
                """
                CREATE TABLE IF NOT EXISTS tyres (
                    id INTEGER PRIMARY KEY,
                    brand TEXT NOT NULL,
                    prefix TEXT NOT NULL DEFAULT '',
                    width INTEGER NOT NULL,
                    ratio INTEGER NOT NULL,
                    rim_size INTEGER NOT NULL,
                    pattern TEXT NOT NULL DEFAULT '',
                    mrp REAL,
                    rcp REAL,
                    invoice_price REAL,
                    source_file TEXT NOT NULL,
                    source_row INTEGER NOT NULL,

                    CHECK (
                        mrp IS NOT NULL
                        OR rcp IS NOT NULL
                        OR invoice_price IS NOT NULL
                    ),

                    UNIQUE (
                        brand, prefix, width,
                        ratio, rim_size, pattern
                    )
                )
            """
            )
            self.con.execute(
                """
                CREATE TABLE IF NOT EXISTS price_history (
                    price_id INTEGER PRIMARY KEY,
                    tyre_id INTEGER NOT NULL REFERENCES tyres(id),
                    mrp REAL,
                    rcp REAL,
                    invoice_price REAL,
                    source_file TEXT NOT NULL,
                    source_row INTEGER NOT NULL,
                    recorded_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP,
                    CHECK (
                        mrp IS NOT NULL
                        OR rcp IS NOT NULL
                        OR invoice_price IS NOT NULL
                    )
                )
            """
            )
            self.con.execute(
                """
                CREATE TRIGGER IF NOT EXISTS tyre_price_history_insert
                AFTER INSERT ON tyres
                BEGIN
                    INSERT INTO price_history (
                        tyre_id,
                        mrp,
                        rcp,
                        invoice_price,
                        source_file,
                        source_row
                    )
                    VALUES (
                        NEW.id,
                        NEW.mrp,
                        NEW.rcp,
                        NEW.invoice_price,
                        NEW.source_file,
                        NEW.source_row
                    );
                END;
            """
            )
            self.con.execute(
                """
                CREATE TRIGGER IF NOT EXISTS tyre_price_history_update
                AFTER UPDATE OF mrp, rcp, invoice_price ON tyres
                WHEN OLD.mrp IS NOT NEW.mrp
                  OR OLD.rcp IS NOT NEW.rcp
                  OR OLD.invoice_price IS NOT NEW.invoice_price
                BEGIN
                    INSERT INTO price_history (
                        tyre_id,
                        mrp,
                        rcp,
                        invoice_price,
                        source_file,
                        source_row
                    )
                    VALUES (
                        NEW.id,
                        NEW.mrp,
                        NEW.rcp,
                        NEW.invoice_price,
                        NEW.source_file,
                        NEW.source_row
                    );
                END;
            """
            )

    def import_tyres(self, tyre_set):
        if not isinstance(tyre_set, TyreSet):
            raise DatabaseError(
                f"Expected a TyreSet() object but got {type(tyre_set).__name__}"
            )
        query = """
            INSERT INTO tyres (
                brand, prefix, width, ratio, rim_size, pattern,
                mrp, rcp, invoice_price, source_file, source_row
            )
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            ON CONFLICT (brand, prefix, width, ratio, rim_size, pattern)
            DO UPDATE SET
                mrp = excluded.mrp,
                rcp = excluded.rcp,
                invoice_price = excluded.invoice_price,
                source_file = excluded.source_file,
                source_row = excluded.source_row
        """

        values = [tyre.to_tuple() for tyre in tyre_set]

        with self.con:
            self.cursor.executemany(query, values)

    def update_or_insert(self, tyre):
        if not isinstance(tyre, Tyre):
            raise DatabaseError(f"Expected a Tyre() object but got {type(tyre).__name__}")
        tyre_set = TyreSet()
        tyre_set.append(tyre)
        self.import_tyres(tyre_set)

    def search(self, order_by="rim_size", ascending=True, **kwargs):
        result = TyreSet()
        query = "SELECT * FROM tyres"
        allowed_columns = {
            "brand",
            "prefix",
            "width",
            "ratio",
            "rim_size",
            "pattern",
            "mrp",
            "rcp",
            "invoice_price",
            "source_file",
            "source_row",
        }
        page = max(kwargs.pop('page', 1), 1)
        offset = (page-1)*self.PAGE_SIZE
        params = ()

        if kwargs:
            invalid_columns = kwargs.keys() - allowed_columns

            if invalid_columns:
                raise DatabaseError(f"Invalid search fields: {invalid_columns}")

            conditions = " AND ".join([f"{col} = ?" for col in kwargs])

            query += f" WHERE {conditions}"
            params = tuple(kwargs.values())

        if order_by not in allowed_columns:
            raise DatabaseError(f"Invalid Order_by field: {order_by}")

        query += f" ORDER BY {order_by}, id"
        if not ascending:
            query += " DESC"

        query += f" LIMIT {self.PAGE_SIZE + 1} OFFSET {offset}"

        with self.con:
            rows = self.cursor.execute(query, params).fetchall()

        for row in rows:
            result.append(Tyre.from_dict(row))

        return result

    def create_user(self, id, username, email, password_hash):
        query = """
                    INSERT or ABORT INTO users(id, username, email, password_hash)
                    VALUES (?, ?, ?, ?)
                """
        try:
            with self.con:
                self.cursor.execute(query, (id, username, email, password_hash))
            return True
        except sqlite3.IntegrityError:
            raise UserAlreadyExists

    def check_username(self, username):
        query = """SELECT EXISTS(SELECT 1 FROM users WHERE username = ?)"""
        with self.con:
            (exists,) = self.cursor.execute(query, (username,)).fetchone()
        return bool(exists)

    def authenticate(self, username, password_hash):
        query = """SELECT id FROM users WHERE username = ? AND password_hash = ?"""
        with self.con:
            res = self.cursor.execute(query, (username, password_hash)).fetchone()

        return res[0]

    def close(self):
        self.cursor.close()
        self.con.close()
