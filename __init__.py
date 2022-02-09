import os
from datetime import timedelta

import requests
from dateutil import parser
from flask import Flask, render_template, request, send_from_directory, session

from authentication.check_token import verify
from config import SENTRY_DSN, SENTRY_SERVER_NAME

# set up sentry for error handling
if SENTRY_DSN != "":
    import sentry_sdk
    from sentry_sdk.integrations.flask import FlaskIntegration

    sentry_sdk.init(
        dsn=SENTRY_DSN,
        integrations=[FlaskIntegration()],
        traces_sample_rate=1.0,
        server_name=SENTRY_SERVER_NAME,
    )


def handle_error(request, session, error_code):
    auth_result = verify(request.headers, session)

    if auth_result:
        headers = {"Authorization": session["access_token"]}

        channel_req = requests.get(
            session.get("server_url") + "?action=channels", headers=headers
        )

        all_channels = channel_req.json()["channels"]
    else:
        all_channels = []

    template = "404.html"

    return (
        render_template(
            template, title="Error", error=error_code, channels=all_channels
        ),
        500,
    )


def create_app():
    app = Flask(__name__)

    app.config["SECRET_KEY"] = os.urandom(32)
    app.config["SQLALCHEMY_DATABASE_URI"] = "sqlite:///microsub.db"
    app.config["SQLALCHEMY_TRACK_MODIFICATIONS"] = False

    # read config.py file
    app.config.from_pyfile(os.path.join(".", "config.py"), silent=False)

    # set maximum lifetime for session
    app.permanent_session_lifetime = timedelta(days=120)

    # blueprint for non-auth parts of app
    from server.main import main as main_blueprint

    app.register_blueprint(main_blueprint)

    from client.client_views import client as client_blueprint

    app.register_blueprint(client_blueprint)

    from authentication.auth import auth as auth_blueprint

    app.register_blueprint(auth_blueprint)

    from server.websub import websub as websub_blueprint

    app.register_blueprint(websub_blueprint)

    from server.server_views import server_views as server_views_blueprint

    app.register_blueprint(server_views_blueprint)

    # filter used to parse dates
    # source: https://stackoverflow.com/questions/4830535/how-do-i-format-a-date-in-jinja2
    @app.template_filter("strftime")
    def _jinja2_filter_datetime(date, fmt=None):
        date = parser.parse(date)
        native = date.replace(tzinfo=None)
        format = "%b %d, %Y"
        return native.strftime(format)

    @app.errorhandler(404)
    def page_not_found(e):
        return handle_error(request, session, 400)

    @app.errorhandler(405)
    def method_not_allowed(e):
        return handle_error(request, session, 405)

    @app.errorhandler(500)
    def server_error():
        handle_error(request, session, 500)

    @app.route("/robots.txt")
    def robots():
        return send_from_directory(app.static_folder, "robots.txt")

    @app.route("/favicon.ico")
    def favicon():
        return send_from_directory(app.static_folder, "favicon.ico")

    @app.route("/manifest.json")
    def web_app_manifest():
        return send_from_directory("static", "manifest.json")

    @app.route("/assets/<path:path>")
    def assets(path):
        return send_from_directory("assets", path)

    # from werkzeug.middleware.profiler import ProfilerMiddleware
    # app.wsgi_app = ProfilerMiddleware(app.wsgi_app, restrictions=[5], profile_dir='./profile')

    return app


create_app()
