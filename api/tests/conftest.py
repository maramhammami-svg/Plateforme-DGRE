"""Configuration commune des tests. Le scan automatique est desactive : en
SQLite, database.py utilise un StaticPool (une seule connexion partagee entre
threads) et la suite dure plus de 60s ; un scan de fond concurrent rendrait
les tests instables."""
import os

os.environ.setdefault("DATABASE_URL", "sqlite:///:memory:")
os.environ.setdefault("AGENT_SCHEDULER_ENABLED", "false")
