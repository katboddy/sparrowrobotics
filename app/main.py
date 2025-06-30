from datetime import datetime
from fastapi import FastAPI, Request, Form, HTTPException
from fastapi.staticfiles import StaticFiles
from fastapi.responses import HTMLResponse
from fastapi.templating import Jinja2Templates
from fastapi.responses import RedirectResponse
from fastapi_mail import FastMail, MessageSchema, ConnectionConfig
from pydantic import EmailStr, SecretStr
from dotenv import load_dotenv
import os
import markdown2
import frontmatter
import logging

# Set up logging at the top of your file
logging.basicConfig(level=logging.DEBUG)
logger = logging.getLogger(__name__)



load_dotenv()

default_email = "example@gmail.com"

# Email Configuration
conf = ConnectionConfig(
    MAIL_USERNAME=os.getenv("MAIL_USERNAME"),
    MAIL_PASSWORD=SecretStr(os.getenv("MAIL_PASSWORD")),
    MAIL_FROM=os.getenv("MAIL_FROM"),
    MAIL_PORT=587,
    MAIL_SERVER="smtp.sendgrid.net",
    MAIL_STARTTLS=True,
    MAIL_SSL_TLS=False,
    USE_CREDENTIALS=True
)

fastmail = FastMail(conf)

app = FastAPI()

app.mount("/static", StaticFiles(directory="app/static"), name="static")
templates = Jinja2Templates(directory="app/templates")

POSTS_DIR = "app/posts"

def get_posts():
    posts = []
    for filename in os.listdir(POSTS_DIR):
        if filename.endswith(".md"):
            with open(os.path.join(POSTS_DIR, filename), "r") as f:
                post = frontmatter.load(f)
                date_str = post.get("date", "1970-01-01")
                date_obj = datetime.strptime(date_str, "%Y-%m-%d")
                posts.append({
                    "title": post["title"],
                    "date": date_str,
                    "date_obj": date_obj,
                    "slug": post["slug"],
                    "summary": post.get("summary", post.content[:150] + "..."),
                    "image": post.get("image", "/static/assets/images/default.jpg"),
                    "content": markdown2.markdown(post.content, extras=["fenced-code-blocks", "code-friendly"])
                })
    posts_sorted = sorted(posts, key=lambda x: x["date_obj"], reverse=True)
    if posts_sorted:
        featured = posts_sorted[0]
        rest = posts_sorted[1:]
    else:
        featured = None
        rest = []

    return featured, rest

@app.get("/", response_class=HTMLResponse)
async def index(request: Request):
    featured, posts = get_posts()
    return templates.TemplateResponse("index.html", {
        "request": request,
        "featured": featured,
        "posts": posts
    })

@app.get("/post/{slug}", response_class=HTMLResponse)
async def post_detail(request: Request, slug: str):
    for filename in os.listdir(POSTS_DIR):
        if filename.endswith(".md"):
            with open(os.path.join(POSTS_DIR, filename), "r") as f:
                post = frontmatter.load(f)
                if post["slug"] == slug:
                    html_content = markdown2.markdown(post.content, extras=["fenced-code-blocks", "code-friendly"])
                    return templates.TemplateResponse("post.html", {
                        "request": request,
                        "title": post["title"],
                        "date": post["date"],
                        "content": html_content,
                        "image": post.get("image")
                    })
    return HTMLResponse(content="Post not found", status_code=404)

@app.get("/about", response_class=HTMLResponse)
async def about_page(request: Request):
    with open("app/posts/about.md", "r") as f:
        post = frontmatter.load(f)
        html_content = markdown2.markdown(post.content, extras=["fenced-code-blocks", "code-friendly"])
        return templates.TemplateResponse("about.html", {
            "request": request,
            "title": post["title"],
            "content": html_content,
            "image": post.get("image")
        })

@app.get("/generic.html", response_class=HTMLResponse)
async def generic_page(request: Request):
    return templates.TemplateResponse("generic.html", {"request": request})

@app.get("/index.html")
async def redirect_to_home():
    return RedirectResponse(url="/")

@app.post("/contact", response_class=HTMLResponse)
async def handle_contact_form(
    request: Request,
    name: str = Form(...),
    email: str = Form(...),
    message: str = Form(...)
):
    try:
        recipient = os.getenv("MAIL_TO")
        if not recipient:
            raise ValueError("MAIL_TO is not set in environment variables")

        logger.debug(f"Mail config: MAIL_USERNAME={conf.MAIL_USERNAME}, MAIL_FROM={conf.MAIL_FROM}")

        message_schema = MessageSchema(
            subject=f"Contact Form Submission from {name}",
            recipients=[recipient],
            body=f"""
                New contact form submission:
                
                Name: {name}
                Email: {email}
                
                Message:
                {message}
            """,
            subtype="plain",
            headers={"Reply-To": email}
        )

        await fastmail.send_message(message_schema)
        logger.info("Email sent successfully")

        return templates.TemplateResponse("contact.html", {
            "request": request,
            "success": True,
            "name": name
        })

    except Exception as e:
        logger.error(f"Failed to send email: {str(e)}", exc_info=True)
        return templates.TemplateResponse("contact.html", {
            "request": request,
            "error": True,
            "message": "Failed to send message. Please try again later."
        })
