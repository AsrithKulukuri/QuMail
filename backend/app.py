from pathlib import Path

from flask import Flask, jsonify, send_from_directory
from flask_cors import CORS

from .config import (
    SECRET_KEY,
    DB_PATH,
    KME_ID,
    DEMO_EMAIL_MODE,
)

from .models import db, User

from .routes.auth_routes import bp as auth_bp
from .routes.key_routes import bp as key_bp
from .routes.mail_routes import bp as mail_bp


def create_app():

    app = Flask(
        __name__,
        static_folder=None
    )

    app.config.update(
        SECRET_KEY=SECRET_KEY,
        SQLALCHEMY_DATABASE_URI=f"sqlite:///{DB_PATH.as_posix()}",
        SQLALCHEMY_TRACK_MODIFICATIONS=False,
    )

    CORS(
        app,
        supports_credentials=True
    )

    db.init_app(app)

    app.register_blueprint(auth_bp)
    app.register_blueprint(key_bp)
    app.register_blueprint(mail_bp)

    # ---------------------------------------------------------
    # FRONTEND
    # ---------------------------------------------------------

    @app.get("/")
    def index():

        return send_from_directory(
            Path(__file__).resolve().parent.parent / "frontend",
            "Qumail_Server.html"
        )

    # ---------------------------------------------------------
    # STATUS
    # ---------------------------------------------------------

    @app.get("/api/status")
    def status():

        return jsonify(
            ok=True,
            service="QuMail",
            kme_id=KME_ID,
            demo_email_mode=DEMO_EMAIL_MODE
        )

    # ---------------------------------------------------------
    # DATABASE INITIALIZATION
    # ---------------------------------------------------------

    with app.app_context():

        db.create_all()

        # Create / repair demo users
        seed()

    return app


def seed():

    """
    Create the demo QuMail users.

    IMPORTANT:
    This function also repairs existing users that do not
    have an ML-KEM key pair.

    Therefore we can safely restart the application without
    destroying the existing database.
    """

    from .encryption_engine import mlkem_generate, mlkem_available

    users = [
        (
            "alice@qumail.demo",
            "alice123",
            "Alice"
        ),
        (
            "bob@qumail.demo",
            "bob123",
            "Bob"
        ),
    ]

    changed = False

    for email, password, name in users:

        user = User.query.filter_by(
            email=email
        ).first()

        # -----------------------------------------------------
        # User does not exist → create it
        # -----------------------------------------------------

        if not user:

            user = User(
                email=email,
                password=password,
                display_name=name
            )

            db.session.add(user)

            # Flush so SQLAlchemy gives the user an ID
            db.session.flush()

            changed = True

        # -----------------------------------------------------
        # Existing user → make sure basic information exists
        # -----------------------------------------------------

        if not user.password:

            user.password = password
            changed = True

        if not user.display_name:

            user.display_name = name
            changed = True

        # -----------------------------------------------------
        # IMPORTANT:
        #
        # Existing users may have been created before ML-KEM
        # was available.
        #
        # Generate the key pair if either key is missing.
        # -----------------------------------------------------

        if not user.pqc_public or not user.pqc_private:

            try:
                private_key, public_key = mlkem_generate()

                user.pqc_private = private_key
                user.pqc_public = public_key

                changed = True

                print(
                    f"[QuMail] ML-KEM key pair ready for {email}"
                )

            except Exception as exc:

                # Do not destroy an existing key if generation
                # fails. L1/L2/L4 can continue to operate.

                print(
                    f"[QuMail] WARNING: Could not generate "
                    f"ML-KEM key pair for {email}: {exc}"
                )

        else:

            print(
                f"[QuMail] ML-KEM key pair already exists for {email}"
            )

    if changed:

        db.session.commit()

    else:

        # Safe even if nothing changed.
        db.session.commit()


# -------------------------------------------------------------
# APPLICATION INSTANCE
# -------------------------------------------------------------

app = create_app()