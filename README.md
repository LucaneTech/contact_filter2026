# CallFilter Pro

Application web pour centres d'appel : upload de contacts, filtrage dynamique, validation téléphonique, export.

## Installation

### 1. Environnement virtuel

```bash
python -m venv .venv
source .venv/bin/activate  # Linux/Mac
# ou .venv\Scripts\activate  # Windows
```

### 2. Dépendances

```bash
pip install -r requirements.txt
```

### 3. Variables d'environnement

```bash
cp .env.example .env
# Éditer .env selon votre configuration
# Pour dev local : laisser USE_SQLITE vide ou True, pas besoin de PostgreSQL
```

### 4. Base de données

```bash
python manage.py migrate
python manage.py setup_demo
```

Cela crée :
- Admin : `admin@callfilter.local` / `admin123`
- Entreprise : `company@callfilter.local` / `admin123`

### 5. Lancer le serveur

```bash
python manage.py runserver
```

Accès : http://localhost:8000

## Traitement asynchrone (Celery)

Pour les uploads lourds :

```bash
# Terminal 1 - Redis (si installé)
redis-server

# Terminal 2 - Celery worker
celery -A contact_filter worker -l info

# Terminal 3 - Celery Beat (nettoyage quotidien)
celery -A contact_filter beat -l info
```

Sans Redis : le traitement s'exécute en synchrone (bloquant).

## Structure

- `apps/accounts` - Auth par email, User personnalisé
- `apps/companies` - Multi-tenant, Company, UploadedFile, ProcessingHistory
- `apps/billing` - Plans, quotas
- `apps/uploads` - Upload, détection colonnes
- `apps/filtering` - Moteur de filtres, validation téléphonique
- `apps/processing` - Tâches Celery
- `apps/exports` - Export CSV/Excel
- `apps/dashboard` - Dashboards entreprise et admin

## Formats supportés

CSV, Excel (.xlsx, .xls), TXT. Mapping automatique des colonnes (téléphone, email, nom, etc.).
