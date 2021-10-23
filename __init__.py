from flask import Flask, render_template, send_from_directory
from dateutil import parser
import os

def create_app():
    app = Flask(__name__)

    app.config['SECRET_KEY'] = os.urandom(32)
    app.config['SQLALCHEMY_DATABASE_URI'] = 'sqlite:///microsub.db'
    app.config['SQLALCHEMY_TRACK_MODIFICATIONS'] = False

    # read config.py file
    app.config.from_pyfile(os.path.join(".", "config.py"), silent=False)

    # blueprint for non-auth parts of app
    from .main import main as main_blueprint

    app.register_blueprint(main_blueprint)

    from .client import client as client_blueprint

    app.register_blueprint(client_blueprint)

    from .auth import auth as auth_blueprint

    app.register_blueprint(auth_blueprint)

    # filter used to parse dates
    # source: https://stackoverflow.com/questions/4830535/how-do-i-format-a-date-in-jinja2
    @app.template_filter('strftime')
    def _jinja2_filter_datetime(date, fmt=None):
        date = parser.parse(date)
        native = date.replace(tzinfo=None)
        format= '%b %d, %Y'
        return native.strftime(format) 

    @app.errorhandler(404)
    def page_not_found(e):
        return render_template("404.html", title="Page not found", error=404), 404

    @app.errorhandler(405)
    def method_not_allowed(e):
        return render_template("404.html", title="Method not allowed", error=405), 405

    @app.errorhandler(500)
    def server_error(e):
        return render_template("404.html", title="Server error", error=500), 500

    @app.route("/robots.txt")
    def robots():
        return send_from_directory(app.static_folder, "robots.txt")

    @app.route("/favicon.ico")
    def favicon():
        return send_from_directory(app.static_folder, "favicon.ico")

    @app.route("/assets/<path:path>")
    def assets(path):
        return send_from_directory("assets", path)

    # from werkzeug.middleware.profiler import ProfilerMiddleware
    # app.wsgi_app = ProfilerMiddleware(app.wsgi_app, restrictions=[5], profile_dir='./profile')

    return app

create_app()