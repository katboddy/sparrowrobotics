# Sparrowrobotics

For detailed development information, see the [Developer Guide](developer_guide.md).

For detailed deployment information, see the [Deployment Guide](deployment_guide.md).


| Command          | What it does                                          |
|------------------|-------------------------------------------------------|
| `make dev`       | Run the dev server with code reloading                |
| `make dev-down`  | Stop and remove dev containers                        |
| `make prod`      | Run the production setup (Gunicorn + Nginx)           |
| `make prod-down` | Stop and remove production setup                      |
| `make clean`     | 🔥 Remove **everything**: images, containers, volumes |
| `make rebuild`   | Clean and restart dev setup                           |