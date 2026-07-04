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

# Statut d'un releve
STATUS_PENDING = "pending"
STATUS_VALIDATED = "validated"
STATUS_REJECTED = "rejected"

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

# Securite comptes
MAX_FAILED_ATTEMPTS = 3
