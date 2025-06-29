# Developer Guide

## Creating a New Blog Post

To create a new blog post, follow these steps:

1. Navigate to the posts directory:
   ```bash
   cd app/posts
   ```

2. Copy the template file to create a new post:
   ```bash
   cp ../post_template/template.md YYYY-MM-DD-post-title.md
   ```
   Replace `YYYY-MM-DD` with the current date and `post-title` with your post's URL-friendly title.
   For example: `2025-06-29-new-feature-announcement.md`

3. Open the new file and update the following front matter:
   ```yaml
   ---
   title: "Your Post Title"
   date: YYYY-MM-DD
   author: "Your Name"
   description: "Brief description of your post"
   tags: ["tag1", "tag2"]
   ---
   ```

4. Write your blog post content below the front matter using Markdown formatting.

5. Save the file and commit it to the repository:
   ```bash
   git add YYYY-MM-DD-post-title.md
   git commit -m "Add new blog post: Your Post Title"
   ```

### Template Structure

The template file located at `app/post_template/template.md` includes:
- Front matter section with metadata
- Placeholder sections for content
- Examples of common Markdown formatting

# Testing Locally

## 1. Install Required Dependencies

First, ensure you have all the necessary dependencies installed:

```bash
pip install -r requirements.txt
```

This will install FastAPI, Uvicorn, Gunicorn, and other required packages.

## 2. Run with Gunicorn

For your specific FastAPI application, the correct command is:

```bash
gunicorn app.main:app -k uvicorn.workers.UvicornWorker -w 4 -b 127.0.0.1:8000
```

Breaking down this command:

- `app.main:app`: This specifies the path to your FastAPI application
  - `app.main` is the Python module path (the `app` directory with the `main.py` file)
  - `:app` refers to the FastAPI instance variable named `app` in your main.py file
- `-k uvicorn.workers.UvicornWorker`: This specifies the worker class - FastAPI requires Uvicorn workers
- `-w 4`: This sets 4 worker processes (you can adjust based on your CPU cores)
- `-b 127.0.0.1:8000`: This binds the server to localhost port 8000

## 3. Development Mode with Auto-reload

For development with automatic reloading when code changes:

```bash
gunicorn app.main:app -k uvicorn.workers.UvicornWorker -w 4 -b 127.0.0.1:8000 --reload
```

## 4. Access Your Application

After starting Gunicorn, you can access your FastAPI application at:
http://127.0.0.1:8000

## 5. Alternative: Direct Uvicorn (for Development)

For simpler development, you can also run directly with Uvicorn:

```bash
uvicorn app.main:app --reload
```

This is simpler but doesn't provide the process management benefits of Gunicorn.

## Note on Production Deployment

Your project is already configured for production deployment using Docker with the command:

```
gunicorn app.main:app -k uvicorn.workers.UvicornWorker -w 4 -b 0.0.0.0:8000
```

You can use `make prod` to run the production setup with Docker as specified in your README.