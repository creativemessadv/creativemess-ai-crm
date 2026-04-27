# YaYa Lady Nail — Sito web

Sito vetrina del centro estetico **YaYa Lady Nail** (Civitanova Marche).

Sito statico HTML/CSS/JS, pensato per essere deployato su Vercel come progetto standalone.

## Struttura

```
.
├── index.html         # Home
├── servizi.html       # Listino servizi
├── gallery.html       # Galleria lavori (22 foto, filtri categoria, lightbox)
├── chi-siamo.html     # Chi siamo
├── contatti.html      # Contatti e prenotazione
├── assets/
│   ├── css/style.css
│   ├── js/main.js
│   └── img/           # Logo, favicon, foto sezioni e galleria
└── vercel.json        # Config clean URLs (/servizi invece di /servizi.html)
```

## Deploy

Il progetto è pronto per il deploy su Vercel:

1. Importa questo repository su Vercel
2. Framework preset: **Other** (sito statico, niente build necessario)
3. Aggiungi il dominio `yayaladynail.it` nelle impostazioni del progetto

Il file `vercel.json` abilita le clean URL automaticamente.

## Sviluppo locale

Apri `index.html` direttamente nel browser, oppure servi la cartella con un server HTTP qualunque, ad esempio:

```bash
python3 -m http.server 8000
```

Poi vai su http://localhost:8000.
