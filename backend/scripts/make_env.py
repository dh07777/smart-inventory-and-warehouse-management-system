"""Create backend/.env from .env.example with freshly generated secrets."""
import secrets, pathlib
root = pathlib.Path(__file__).resolve().parent.parent
src, dst = root / ".env.example", root / ".env"
if dst.exists():
    print(".env already exists - not overwritten."); raise SystemExit
text = src.read_text()
text = text.replace("SECRET_KEY=\n", f"SECRET_KEY={secrets.token_hex(32)}\n", 1)
text = text.replace("JWT_SECRET_KEY=\n", f"JWT_SECRET_KEY={secrets.token_hex(32)}\n", 1)
dst.write_text(text); print("Created", dst)
