# CLEAN Data API

A FastAPI application providing access to enzyme kinetic data from the CLEAN database.

## Local Setup

1. Clone the repository:

2. Configure environment variables:
   ```bash
   cp .env.example .env
   # Edit .env file with your database credentials if needed
   ```
3. Forward DB service:
    ```bash
   kubectl port-forward -n moldb service/moldb-postgres-rw 5433:5432
   ```

3. Build and start the services:
   ```bash
   docker-compose up -d
   ```

4. Access the API documentation at http://localhost:8000/api/v1/docs or http://localhost:8000/api/v1/redoc