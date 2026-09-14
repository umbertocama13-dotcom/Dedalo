# Dedalo

Assistente di troubleshooting guidato per impianti e linee produttive (PoC).
Matching sintomo → diagnosi deterministico, contestualizzato su famiglia di prodotto e fase del ciclo di lavoro.

> Il README è in costruzione e verrà completato man mano che il progetto avanza (backend, frontend, test).

## Requisiti

- Python 3.11+ (sviluppato con 3.12)
- MySQL 8 o MariaDB

## Setup del database

Crea i database `dedalo` e `dedalo_test` e un utente con permessi su entrambi. Poi, dalla root del progetto:

```bash
mysql -u dedalo -p dedalo < database/schema.sql
mysql -u dedalo -p dedalo < database/seed.sql
```

`schema.sql` elimina e ricrea tutte le tabelle: rieseguirlo cancella i dati presenti.

## Configurazione

```bash
cp backend/.env.example backend/.env
```

Poi inserisci in `backend/.env` le credenziali MySQL reali e una `JWT_SECRET_KEY`. Il file `.env` è ignorato da Git e non va mai committato.

## Utenti di test

Il seed crea due utenti demo, uno per ruolo:

| Ruolo | Username | Password | Cosa può fare |
|---|---|---|---|
| `expert` | `expert_demo` | `expert123` | consulta e modifica la knowledge base (sintomi, cause, soluzioni, eccezioni) |
| `operator` | `operator_demo` | `operator123` | consulta tramite chat, nessuna scrittura |

⚠️ Queste credenziali servono **solo per lo sviluppo locale**. Prima di qualsiasi uso su una linea reale gli utenti demo vanno rimossi o le loro password cambiate.
