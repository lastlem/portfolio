# Photofolio

This is a portfolio website with photo uploading and downloading features.

## How to run using Docker

1. Ensure you have Docker and Docker Compose installed.
2. In the root directory (where `docker-compose.yml` is located), run the following command to build and start the containers in the background:
   ```bash
   docker-compose up -d --build
   ```
3. The application will be accessible at `http://localhost:5000`.
4. To stop the containers, run:
   ```bash
   docker-compose down
   ```

### Default Credentials / Configuration

To log in as an administrator to create albums and upload photos, go to `http://localhost:5000/admin/<ADMIN_SECRET>`, where `<ADMIN_SECRET>` is `admin-secret` by default (unless overridden in a `.env` file).
