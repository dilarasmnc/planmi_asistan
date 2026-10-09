import os

from app import create_app

# Gunicorn (Render) "run:app" diyerek bu değişkeni bulur
app = create_app()

if __name__ == "__main__":
    # Sadece bilgisayarında "python run.py" ile çalışırken devreye girer
    app.run(
        debug=app.config["DEBUG"],
        port=int(os.environ.get("PORT", 5000)),
    )