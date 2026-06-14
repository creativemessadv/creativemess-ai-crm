# =====================================================================
#  database.py - Gestione del database locale SQLite
# ---------------------------------------------------------------------
#  Questo modulo si occupa SOLO di leggere/scrivere dati. Non sa nulla
#  di prezzi o di Google Trends: riceve dati e li salva, oppure li
#  restituisce su richiesta. Così il resto del codice resta pulito.
#
#  Tabelle:
#    carte        -> anagrafica delle carte (nome, set, immagine...)
#    prezzi       -> uno "scatto" di prezzo per carta/giorno/fonte
#    trends       -> valore di interesse Google Trends per parola/giorno
#    carte_calde  -> risultato dell'analisi: le carte segnalate ogni giorno
# =====================================================================

import sqlite3
from pathlib import Path


def connetti(db_path: Path) -> sqlite3.Connection:
    """Apre (e se serve crea) il database SQLite e restituisce la connessione.

    Usa row_factory in modo da poter leggere le colonne per nome
    (es. riga["nome"]) invece che per posizione.
    """
    conn = sqlite3.connect(db_path)
    conn.row_factory = sqlite3.Row
    return conn


def inizializza_schema(conn: sqlite3.Connection) -> None:
    """Crea le tabelle se non esistono ancora. Sicuro da chiamare ogni volta."""
    conn.executescript(
        """
        -- Anagrafica delle carte monitorate.
        CREATE TABLE IF NOT EXISTS carte (
            id            TEXT PRIMARY KEY,   -- es. "sv3pt5-199"
            nome          TEXT NOT NULL,
            set_id        TEXT,
            set_nome      TEXT,
            numero        TEXT,
            rarita        TEXT,
            immagine_url  TEXT,
            aggiornato_il TEXT
        );

        -- Uno scatto di prezzo per carta, giorno, fonte e variante.
        -- La UNIQUE evita doppioni se rilanci lo script più volte al giorno.
        CREATE TABLE IF NOT EXISTS prezzi (
            id             INTEGER PRIMARY KEY AUTOINCREMENT,
            carta_id       TEXT NOT NULL,
            data           TEXT NOT NULL,     -- formato YYYY-MM-DD
            fonte          TEXT NOT NULL,     -- "tcgplayer" o "cardmarket"
            variante       TEXT,              -- es. "holofoil", "normal"
            prezzo_market  REAL,              -- prezzo di riferimento
            prezzo_basso   REAL,
            prezzo_alto    REAL,
            cm_avg1        REAL,              -- media Cardmarket ultimo giorno
            cm_avg7        REAL,              -- media Cardmarket ultimi 7 giorni
            cm_avg30       REAL,              -- media Cardmarket ultimi 30 giorni
            cm_trend       REAL,              -- prezzo "trend" di Cardmarket
            UNIQUE (carta_id, data, fonte, variante)
        );

        -- Valori di interesse di Google Trends.
        CREATE TABLE IF NOT EXISTS trends (
            id        INTEGER PRIMARY KEY AUTOINCREMENT,
            keyword   TEXT NOT NULL,
            data      TEXT NOT NULL,          -- formato YYYY-MM-DD
            interesse INTEGER,                -- 0-100 secondo Google
            UNIQUE (keyword, data)
        );

        -- Risultato dell'analisi giornaliera: le carte "calde".
        CREATE TABLE IF NOT EXISTS carte_calde (
            id             INTEGER PRIMARY KEY AUTOINCREMENT,
            data           TEXT NOT NULL,
            carta_id       TEXT NOT NULL,
            punteggio      REAL,
            variazione_pct REAL,
            motivo         TEXT,
            UNIQUE (data, carta_id)
        );
        """
    )
    conn.commit()


# ---------------------------------------------------------------------
# SCRITTURA
# ---------------------------------------------------------------------

def salva_carta(conn: sqlite3.Connection, carta: dict) -> None:
    """Inserisce o aggiorna l'anagrafica di una carta.

    'carta' è un dizionario con le chiavi: id, nome, set_id, set_nome,
    numero, rarita, immagine_url, aggiornato_il.
    """
    conn.execute(
        """
        INSERT INTO carte (id, nome, set_id, set_nome, numero, rarita,
                           immagine_url, aggiornato_il)
        VALUES (:id, :nome, :set_id, :set_nome, :numero, :rarita,
                :immagine_url, :aggiornato_il)
        ON CONFLICT(id) DO UPDATE SET
            nome          = excluded.nome,
            set_id        = excluded.set_id,
            set_nome      = excluded.set_nome,
            numero        = excluded.numero,
            rarita        = excluded.rarita,
            immagine_url  = excluded.immagine_url,
            aggiornato_il = excluded.aggiornato_il
        """,
        carta,
    )


def salva_prezzo(conn: sqlite3.Connection, prezzo: dict) -> None:
    """Inserisce uno scatto di prezzo. Se esiste già (stessa carta/giorno/
    fonte/variante) lo aggiorna con i valori più recenti."""
    conn.execute(
        """
        INSERT INTO prezzi (carta_id, data, fonte, variante, prezzo_market,
                            prezzo_basso, prezzo_alto, cm_avg1, cm_avg7,
                            cm_avg30, cm_trend)
        VALUES (:carta_id, :data, :fonte, :variante, :prezzo_market,
                :prezzo_basso, :prezzo_alto, :cm_avg1, :cm_avg7,
                :cm_avg30, :cm_trend)
        ON CONFLICT(carta_id, data, fonte, variante) DO UPDATE SET
            prezzo_market = excluded.prezzo_market,
            prezzo_basso  = excluded.prezzo_basso,
            prezzo_alto   = excluded.prezzo_alto,
            cm_avg1       = excluded.cm_avg1,
            cm_avg7       = excluded.cm_avg7,
            cm_avg30      = excluded.cm_avg30,
            cm_trend      = excluded.cm_trend
        """,
        prezzo,
    )


def salva_trend(conn: sqlite3.Connection, keyword: str, data: str, interesse: int) -> None:
    """Salva il valore di interesse Google Trends per una parola in un giorno."""
    conn.execute(
        """
        INSERT INTO trends (keyword, data, interesse)
        VALUES (?, ?, ?)
        ON CONFLICT(keyword, data) DO UPDATE SET interesse = excluded.interesse
        """,
        (keyword, data, interesse),
    )


def salva_carta_calda(conn: sqlite3.Connection, calda: dict) -> None:
    """Salva una riga del report 'carte calde' del giorno."""
    conn.execute(
        """
        INSERT INTO carte_calde (data, carta_id, punteggio, variazione_pct, motivo)
        VALUES (:data, :carta_id, :punteggio, :variazione_pct, :motivo)
        ON CONFLICT(data, carta_id) DO UPDATE SET
            punteggio      = excluded.punteggio,
            variazione_pct = excluded.variazione_pct,
            motivo         = excluded.motivo
        """,
        calda,
    )


# ---------------------------------------------------------------------
# LETTURA (servono all'analisi e alla futura dashboard)
# ---------------------------------------------------------------------

def prezzo_piu_recente_prima_di(conn, carta_id, fonte, variante, data):
    """Restituisce il prezzo di mercato più recente PRECEDENTE a 'data'
    per la stessa carta/fonte/variante, oppure None se non c'è storico."""
    riga = conn.execute(
        """
        SELECT prezzo_market, data
        FROM prezzi
        WHERE carta_id = ? AND fonte = ? AND variante = ? AND data < ?
        ORDER BY data DESC
        LIMIT 1
        """,
        (carta_id, fonte, variante, data),
    ).fetchone()
    return riga


def prezzi_del_giorno(conn, data):
    """Restituisce tutti gli scatti di prezzo registrati in un certo giorno,
    già uniti all'anagrafica della carta (nome, set...)."""
    return conn.execute(
        """
        SELECT p.*, c.nome, c.set_nome, c.rarita, c.immagine_url
        FROM prezzi p
        JOIN carte c ON c.id = p.carta_id
        WHERE p.data = ?
        """,
        (data,),
    ).fetchall()


def carte_calde_del_giorno(conn, data):
    """Restituisce le carte calde di un certo giorno, ordinate per punteggio."""
    return conn.execute(
        """
        SELECT cc.*, c.nome, c.set_nome, c.rarita, c.immagine_url
        FROM carte_calde cc
        JOIN carte c ON c.id = cc.carta_id
        WHERE cc.data = ?
        ORDER BY cc.punteggio DESC
        """,
        (data,),
    ).fetchall()


def trends_del_giorno(conn, data):
    """Restituisce i valori Google Trends di un certo giorno."""
    return conn.execute(
        "SELECT keyword, interesse FROM trends WHERE data = ? ORDER BY interesse DESC",
        (data,),
    ).fetchall()
