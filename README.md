# PyArchInit Web Viewer

Web application for viewing archaeological data from PyArchInit databases.

## Features

- **Archaeological Data Viewing**: Browse Sites, US (Stratigraphic Units), Materials, and Pottery records
- **Media Integration**: View images and media via PyArchInit Storage Server
- **Materials Inventory**: Summary view of materials by storage location and box
- **Export**: Export data to PDF and Excel formats
- **Dashboard**: Statistics and charts for data overview

## Requirements

- Python 3.9+
- PostgreSQL database with PyArchInit schema
- PyArchInit Storage Server for media files

## Installation

### Local Development

1. Clone the repository:
```bash
git clone https://github.com/enzococca/pyarchinit-webapp.git
cd pyarchinit-webapp
```

2. Create virtual environment:
```bash
cd backend
python -m venv venv
source venv/bin/activate  # On Windows: venv\Scripts\activate
```

3. Install dependencies:
```bash
pip install -r requirements.txt
```

4. Configure environment:
```bash
cp ../.env.example .env
# Edit .env with your database and storage server settings
```

5. Run the application:
```bash
uvicorn app.main:app --reload
```

6. Open http://localhost:8000 in your browser

### Railway Deployment

1. Create a new project on Railway
2. Connect your GitHub repository
3. Add environment variables:
   - `DATABASE_URL`: Your PostgreSQL connection string
   - `STORAGE_SERVER_URL`: PyArchInit Storage Server URL
   - `STORAGE_API_KEY`: API key for storage server
4. Deploy

## API Documentation

Once running, API documentation is available at:
- Swagger UI: `/api/docs`
- ReDoc: `/api/redoc`

## API Endpoints

- `GET /api/sites` - List archaeological sites
- `GET /api/us` - List stratigraphic units
- `GET /api/materiali` - List materials inventory
- `GET /api/materiali/summary` - Materials summary by storage/box
- `GET /api/pottery` - List pottery records
- `GET /api/media/for-entity/{type}/{id}` - Get media for entity
- `GET /api/export/{entity}/excel` - Export to Excel
- `GET /api/export/{entity}/pdf` - Export to PDF

## License

GPL v2 - See LICENSE file for details.

## Author

PyArchInit Team
