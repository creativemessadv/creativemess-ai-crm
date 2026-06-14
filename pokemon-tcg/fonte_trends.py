# =====================================================================
#  fonte_trends.py - Lettura interesse da Google Trends (pytrends)
# ---------------------------------------------------------------------
#  NOTA SUI TERMINI D'USO:
#  Google non offre un'API pubblica ufficiale per Trends. La libreria
#  'pytrends' interroga l'endpoint interno usato dal sito. Per un uso
#  PERSONALE e a BASSO VOLUME (una manciata di chiamate al giorno) è una
#  pratica comune e tollerata, ma resta una zona grigia.
#
#  Alternativa 100% ufficiale (fallback manuale):
#    1. vai su https://trends.google.it/trends/explore
#    2. cerca le tue parole chiave, esporta il CSV
#    3. importalo a mano (possiamo aggiungere un piccolo importatore CSV)
#
#  Se pytrends dovesse fallire (rate limit, blocco), il sistema NON si
#  blocca: salta semplicemente la parte Trends e continua con i prezzi.
# =====================================================================

from datetime import date


def scarica_interesse(keywords: list[str], paese: str = "", periodo: str = "now 7-d") -> dict:
    """Restituisce un dizionario {parola_chiave: valore_interesse_0_100}.

    'valore_interesse' è l'ultimo valore disponibile nel periodo scelto,
    su scala 0-100 come la usa Google Trends.

    In caso di errore o di libreria non installata, restituisce un
    dizionario vuoto e stampa un avviso (senza interrompere il programma).
    """
    if not keywords:
        return {}

    # Importiamo pytrends qui dentro così, se non è installato, l'errore
    # riguarda solo questa funzione e non l'intero programma.
    try:
        from pytrends.request import TrendReq
    except ImportError:
        print("  [ATTENZIONE] pytrends non installato: salto Google Trends.")
        print("              Installa con: pip install pytrends")
        return {}

    # Google Trends accetta al massimo 5 parole chiave per richiesta.
    keywords = keywords[:5]

    try:
        pytrends = TrendReq(hl="it-IT", tz=0)
        pytrends.build_payload(keywords, timeframe=periodo, geo=paese)
        dataframe = pytrends.interest_over_time()
    except Exception as errore:  # pytrends può lanciare errori vari
        print(f"  [ATTENZIONE] Google Trends non raggiungibile: {errore}")
        return {}

    if dataframe is None or dataframe.empty:
        print("  [ATTENZIONE] Google Trends non ha restituito dati.")
        return {}

    # Prendiamo l'ULTIMA riga (il valore più recente) per ogni parola.
    ultima_riga = dataframe.iloc[-1]
    risultato: dict[str, int] = {}
    for parola in keywords:
        if parola in ultima_riga:
            risultato[parola] = int(ultima_riga[parola])
    return risultato


def oggi() -> str:
    """Data odierna in formato YYYY-MM-DD (usata come chiave dei dati)."""
    return date.today().isoformat()
