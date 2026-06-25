# Plateforme DGRE — Banc d'essai (pluviométrie)

PoC instrumenté servant de socle à l'**agent intelligent de surveillance, d'audit
et de contrôle qualité des flux de données**.

Principe directeur : **tout flux passe par un point observable**. Chaque action
émet un **événement normalisé** (le *contrat d'observabilité*) dans la table
`events` — l'unique interface que l'agent lira plus tard.

> Version 0.2.0 — phase 1 (plateforme complète) intégrée.

## Architecture

```
Client → Passerelle nginx (:8080) → API FastAPI (:8000) → PostgreSQL
                                          └── un événement normalisé par action
```

| Couche | Implémentation |
|--------|----------------|
| Passerelle / point d'observation | nginx (`gateway/nginx.conf`) |
| API + authentification + rôles | FastAPI + JWT (`api/app`) |
| Données | PostgreSQL (`Station`, `Reading`, `ReadingVersion`) |
| Observabilité | table `events` + helper `log_event` |

## Lancer

```bash
docker compose up --build
```

- Docs interactifs (Swagger) : http://localhost:8080/docs
- Santé : http://localhost:8080/health

Tables créées et données de départ injectées automatiquement.

## Comptes de départ

| Identifiant | Mot de passe | Rôle | Région |
|-------------|--------------|------|--------|
| `admin` | `admin123` | administrateur | National |
| `resp_nord` | `resp123` | responsable | Nord |
| `agent_nord` | `agent123` | agent | Nord |
| `agent_sud` | `agent123` | agent | Sud |

Stations : `ST-001`, `ST-002` (Nord), `ST-003` (Sud).

## Endpoints

| Méthode | Route | Rôle | Rôle |
|---------|-------|------|------|
| POST | `/auth/login` | tous | connexion (JWT) |
| GET | `/auth/me` | connecté | profil courant |
| GET / POST | `/stations` | lecture: tous · création: responsable+ | stations |
| PATCH | `/stations/{id}` | responsable+ | modifier / désactiver |
| GET / POST | `/readings` | agent+ | lister / saisir |
| PATCH | `/readings/{id}` | agent (sien) / responsable+ | **corriger (versionné)** |
| DELETE | `/readings/{id}` | responsable+ | supprimer |
| GET | `/readings/{id}/versions` | agent+ | **historique des modifications** |
| POST | `/readings/{id}/validate` | responsable+ | valider / rejeter |
| POST | `/readings/import` | agent+ | **import CSV** |
| GET | `/readings/export` | agent+ | **export CSV** |
| GET / POST | `/admin/users` | administrateur | **gestion des comptes** |
| PATCH | `/admin/users/{id}` | administrateur | rôle / région / activation |
| GET | `/events` | administrateur | journal global |

Import CSV attendu : colonnes `station_code,date,value_mm`.

## Nouveautés de la phase 1

- **Historique des versions des relevés** (`reading_versions`) : chaque correction
  enregistre l'ancienne et la nouvelle valeur, l'auteur et la raison — la trace fine
  qui permettra de détecter et d'auditer les **falsifications**.
- **CRUD complet** : correction et suppression de relevés, modification et
  désactivation de stations.
- **Import / export CSV** des relevés (le volume exporté est journalisé).
- **Module d'administration** : création de comptes, changement de rôle / région /
  activation (actions sensibles journalisées en détail).

## Comportements anormaux déjà instrumentés

Chacun laisse un événement `denied` / `failure` dans le journal — les **signaux**
que l'agent apprendra à détecter :

| Tentative | Événement | Cas métier |
|-----------|-----------|-----------|
| Saisie / accès hors de sa région | `*` / `denied` | accès non autorisé |
| Agent qui valide un relevé | `validate_reading` / `denied` | abus de privilège |
| Agent qui modifie un relevé **validé** | `update_reading` / `denied` | falsification |
| Valeur de 900 mm | `create_reading` / `failure` | valeur aberrante |
| Connexions échouées en rafale | `login` / `failure` (répété) | brute-force |
| Export de gros volumes | `export_readings` (volume élevé) | exfiltration |
| Non-admin sur `/admin/*` ou `/events` | `denied` | accès interdit |

## Structure

```
plateforme-dgre/
├── docker-compose.yml
├── gateway/nginx.conf
└── api/
    ├── Dockerfile
    ├── requirements.txt
    └── app/
        ├── main.py
        ├── config.py · database.py · constants.py
        ├── models.py      # User, Station, Reading, ReadingVersion, Event
        ├── security.py · deps.py · schemas.py · events.py · seed.py
        └── routers/       # auth, stations, readings, events, admin
```

## Prochaines étapes (feuille de route)

2. Générer le trafic (workflows légitimes + scénarios d'attaque) pour peupler `events`.
3. Contrôle qualité avancé (complétude, cohérence spatiale, doublons, valeur figée).
4. Développer l'agent qui lit `events` : détection sécurité + contrôle qualité.
