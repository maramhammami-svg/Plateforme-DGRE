# Roles
ROLE_AGENT = "agent"
ROLE_OBSERVATEUR = "observateur"
ROLE_RESPONSABLE = "responsable"
ROLE_ANALYSTE = "analyste"
ROLE_DIRECTEUR = "directeur"
ROLE_ADMIN = "administrateur"
ROLES = {ROLE_AGENT, ROLE_OBSERVATEUR, ROLE_RESPONSABLE, ROLE_ANALYSTE, ROLE_DIRECTEUR, ROLE_ADMIN}

# Type de station
STATION_TYPE_AUTO = "automatique"
STATION_TYPE_CONV = "conventionnelle"
STATION_TYPES = {STATION_TYPE_AUTO, STATION_TYPE_CONV}

# Parametre mesure
PARAM_PLUVIO = "pluviometrie"
PARAM_LIMNI = "limnimetrie"
PARAMETERS = {PARAM_PLUVIO, PARAM_LIMNI}

# Unite de mesure
UNIT_MM = "mm"
UNIT_CM = "cm"
UNITS = {UNIT_MM, UNIT_CM}

# Unite organisationnelle DGRE
UNITE_DIRECTION = "direction"
UNITE_DEPARTEMENT = "departement"
UNITE_SOUS_DEPT = "sous_departement"
UNITE_SERVICE = "service"
UNITE_TYPES = {UNITE_DIRECTION, UNITE_DEPARTEMENT, UNITE_SOUS_DEPT, UNITE_SERVICE}

# Statut d'une station
STATION_STATUS_ACTIVE = "active"
STATION_STATUS_INACTIVE = "inactive"
STATION_STATUSES = {STATION_STATUS_ACTIVE, STATION_STATUS_INACTIVE}

# Statut du capteur (etat de transmission, distinct du statut administratif de la station)
SENSOR_STATUS_OPERATIONAL = "operational"
SENSOR_STATUS_DEGRADED = "degraded"
SENSOR_STATUS_OFFLINE = "offline"
SENSOR_STATUS_UNKNOWN = "unknown"
SENSOR_STATUSES = {SENSOR_STATUS_OPERATIONAL, SENSOR_STATUS_DEGRADED, SENSOR_STATUS_OFFLINE, SENSOR_STATUS_UNKNOWN}

# Statut d'un releve
STATUS_PENDING = "pending"
STATUS_VALIDATED = "validated"
STATUS_REJECTED = "rejected"
STATUSES = {STATUS_PENDING, STATUS_VALIDATED, STATUS_REJECTED}

# Source d'un releve
SOURCE_AUTO = "ingere_auto"
SOURCE_MANUAL = "saisie_manuelle"
SOURCE_IMPORT = "importe"
SOURCES = {SOURCE_AUTO, SOURCE_MANUAL, SOURCE_IMPORT}

# Flags qualite
FLAG_OK = "ok"
FLAG_SUSPECT = "suspect"
FLAG_ABERRANT = "aberrant"
FLAG_MANQUANT = "manquant"
QUALITY_FLAGS = {FLAG_OK, FLAG_SUSPECT, FLAG_ABERRANT, FLAG_MANQUANT}

# Resultat d'un evenement (contrat d'observabilite)
RESULT_SUCCESS = "success"
RESULT_FAILURE = "failure"
RESULT_DENIED = "denied"

# Seuils qualite de depart (a calibrer)
PLAUSIBLE_MAX_MM = 350.0   # > rejet (saisie manuelle)
SUSPECT_MAX_MM = 200.0     # > signalement (mais accepte)

# Seuils qualite limnimetrie (cm) — PLACEHOLDERS, A CALIBRER avec Amie / donnees reelles
SUSPECT_MAX_CM = 500.0     # > signalement (mais accepte)
PLAUSIBLE_MAX_CM = 1000.0  # > rejet / aberrant

# Securite comptes
MAX_FAILED_ATTEMPTS = 3

# Bornes anti-DoS / entrees malformees
MAX_IMPORT_CSV_BYTES = 5 * 1024 * 1024   # 5 Mo
MAX_IMPORT_CSV_ROWS = 50_000
MAX_BATCH_POINTS = 5_000
MAX_DOCUMENT_BYTES = 10 * 1024 * 1024    # 10 Mo

# Agent de surveillance : severite des alertes
SEVERITY_CRITICAL = "critical"
SEVERITY_HIGH = "high"
SEVERITY_MEDIUM = "medium"

# Agent de surveillance : statut d'une alerte
ALERT_OPEN = "open"
ALERT_ACKNOWLEDGED = "acknowledged"
ALERT_RESOLVED = "resolved"
ALERT_FALSE_POSITIVE = "false_positive"

# Agent de surveillance : actions automatiques
AUTO_ACTION_LOCK = "lock_account"
AUTO_ACTION_BLOCK_EXPORT = "block_export"
AUTO_ACTION_FORCE_RELOGIN = "force_relogin"

# Agent de surveillance : seuils des regles
BRUTE_FORCE_THRESHOLD = 5          # echecs de connexion sur le meme compte
BRUTE_FORCE_WINDOW_SEC = 120
SCAN_THRESHOLD = 10                # comptes distincts tentes depuis la meme IP
SCAN_WINDOW_SEC = 300
ESCALATION_THRESHOLD = 3           # acces refuses (403) pour le meme acteur
ESCALATION_WINDOW_SEC = 600
EXFILTRATION_VOLUME = 10000        # volume (lignes/ko) exporte en un seul evenement
NIGHT_START_HOUR = 22              # acces hors plage [6h-22h[ = signal
NIGHT_END_HOUR = 6
ACTIVITY_SPIKE_MULTIPLIER = 3      # volume recent >= multiplicateur x moyenne habituelle
