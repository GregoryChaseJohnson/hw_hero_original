# hw-hero Renderer

## Run locally

Create the virtual environment:

```bash
python3 -m venv .venv
```

Install dependencies into the virtual environment:

```bash
.venv/bin/pip install -r requirements.txt
```

Run the Flask app:

```bash
.venv/bin/python app.py
```

The app will start in development mode on `http://127.0.0.1:5000` by default.

## Notes

- The QR code upload flow requires the `qrcode` and `Pillow` packages listed in `requirements.txt`.
- Authentication is session-based on the Flask server.
- For deployment, set a real `FLASK_SECRET_KEY` in the environment.
