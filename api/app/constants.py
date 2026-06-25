# Roles
ROLE_AGENT = "agent"
ROLE_RESPONSABLE = "responsable"
ROLE_ADMIN = "administrateur"
ROLES = {ROLE_AGENT, ROLE_RESPONSABLE, ROLE_ADMIN}

# Statut d'un releve
STATUS_PENDING = "pending"
STATUS_VALIDATED = "validated"
STATUS_REJECTED = "rejected"

# Resultat d'un evenement (contrat d'observabilite)
RESULT_SUCCESS = "success"
RESULT_FAILURE = "failure"
RESULT_DENIED = "denied"

# Seuils qualite de depart (a calibrer)
PLAUSIBLE_MAX_MM = 350.0   # > rejet
SUSPECT_MAX_MM = 200.0     # > signalement (mais accepte)
