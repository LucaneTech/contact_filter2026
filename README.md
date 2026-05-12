# CallFilter Pro

Application web Django pour centres d'appel : import de fichiers contacts, filtrage dynamique, validation téléphonique et export — avec gestion multi-entreprises, quotas et abonnements.

## Stack technique

- **Backend** : Django 6.0.3, Celery, Redis
- **Base de données** : SQLite (dev) / PostgreSQL (prod)
- **Frontend** : Tailwind CSS, django-lucide, django-jazzmin (admin)
- **Traitement données** : pandas, numpy, openpyxl, phonenumbers
- **Paiement** : Stripe
- **Infra dev** : Docker Compose (Redis + Redis Commander)

## Installation

### 1. Environnement virtuel

```bash
python -m venv env
source env/bin/activate        # Linux/Mac
# ou env\Scripts\activate      # Windows
```

### 2. Dépendances

```bash
pip install -r requirements.txt
```

### 3. Variables d'environnement

```bash
cp .env.example .env
# Éditer .env selon votre configuration
# En dev local : laisser USE_SQLITE=True, PostgreSQL non requis
```

### 4. Base de données

```bash
python manage.py migrate
python manage.py setup_demo
```

Crée les comptes de démo :
- Admin : `admin@callfilter.local` / `admin123`
- Entreprise : `company@callfilter.local` / `admin123`

### 5. Lancer le serveur

```bash
python manage.py runserver
```

Accès : http://localhost:8000

## Traitement asynchrone (Celery + Redis)

Nécessaire pour les uploads volumineux. Sans Redis, le traitement s'exécute en synchrone.

```bash
# Terminal 1 — Redis via Docker
docker compose up redis

# Terminal 2 — Celery worker
celery -A contact_filter worker -l info

# Terminal 3 — Celery Beat (nettoyage planifié)
celery -A contact_filter beat -l info
```

Redis Commander (interface web) disponible sur http://localhost:8081 après `docker compose up`.

## Fonctionnalités

- **Import** : CSV, Excel (.xlsx, .xls), TXT — détection et mapping automatique des colonnes (téléphone, email, nom…)
- **Filtrage** : moteur de règles dynamiques par colonne et valeur
- **Validation téléphonique** : normalisation et vérification des numéros via `phonenumbers`
- **Export** : CSV et Excel des contacts filtrés
- **Multi-tenant** : isolation des données par entreprise
- **Billing** : plans d'abonnement avec quotas mensuels de contacts et intégration Stripe
- **Dashboard** : vues séparées entreprise et administrateur
- **Admin** : interface Jazzmin avec historique des traitements

## Structure des apps

| App | Rôle |
|-----|------|
| `apps/accounts` | Authentification par email, modèle User personnalisé |
| `apps/companies` | Multi-tenant, Company, UploadedFile, historique |
| `apps/billing` | Plans, quotas mensuels, intégration Stripe |
| `apps/uploads` | Upload de fichiers, détection de colonnes |
| `apps/filtering` | Moteur de filtres et règles de validation |
| `apps/processing` | Tâches Celery pour le traitement asynchrone |
| `apps/exports` | Génération des exports CSV/Excel |
| `apps/dashboard` | Dashboards entreprise et admin |
