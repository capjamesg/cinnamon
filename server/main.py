import requests
from flask import (
    Blueprint,
    abort,
    flash,
    jsonify,
    redirect,
    render_template,
    request,
    session,
)

from actions.channels import (
    create_channel,
    delete_channel,
    get_channels,
    reorder_channels,
    update_channel,
)
from actions.following import create_follow, get_follow, unfollow
from actions.preview import preview
from actions.react import mark_as_read, react
from actions.search import search_for_content, search_for_feeds
from actions.timeline import get_post, get_timeline, remove_entry
from actions.user_ops import block, get_muted, mute, unblock, unmute
from authentication.check_token import verify as check_token

main = Blueprint("main", __name__, template_folder="templates")


def process_get_request(request: request, action: str, identifier: str, channel: str):
    if action == "timeline" and not identifier:
        return get_timeline(request)
    elif action == "timeline" and identifier:
        return get_post(request)
    elif action == "follow":
        return get_follow(channel)
    elif action == "mute":
        return get_muted(request)
    elif action == "channels":
        return get_channels()
    elif action == "search" and not channel:
        return search_for_feeds(request)
    elif action == "search" and channel:
        return search_for_content(request)


def process_channels(request: request, method: str):
    if request.form.get("name") and request.form.get("channel"):
        return update_channel(request)

    if request.form.get("channels") and method == "order":
        return reorder_channels(request)

    if method == "delete":
        return delete_channel()

    return create_channel()


def process_post_user_actions(request: request, action: str):
    if action == "follow":
        return create_follow(request)
    elif action == "unfollow":
        return unfollow(request)
    elif action == "block":
        return block(request)
    elif action == "unblock":
        return unblock(request)
    elif action == "mute":
        return mute(request)
    elif action == "unmute":
        return unmute(request)


def process_post_request(request: request, action: str, method: str):
    if action == "timeline" and method == "remove":
        return remove_entry(request)
    elif action == "timeline":
        return mark_as_read(request)
    elif action == "preview":
        return preview(request)
    elif action == "react":
        return react(request)
    elif action == "channels":
        process_channels(request, method)

    process_post_user_actions(request, action)


def microsub_api_request(post_data, success_message):
    request = requests.post(
        session.get("server_url"),
        data=post_data,
        headers={"Authorization": "Bearer " + session["access_token"]},
    )

    if request.status_code == 200:
        flash(success_message)
    else:
        flash(request.json()["error"])


@main.route("/")
def index():
    is_authenticated = check_token(request.headers, session)

    if is_authenticated:
        return redirect("/reader/all")

    return render_template("index.html", title="Home", channels=[])


@main.route("/setup")
def setup():
    return render_template("setup.html", title="Setup", channels=[])


@main.route("/endpoint", methods=["GET", "POST"])
def home():
    if request.form:
        action = request.form.get("action")
        method = request.form.get("method")
        channel = request.form.get("channel")
        identifier = request.form.get("id")
    else:
        action = request.args.get("action")
        method = request.args.get("method")
        channel = request.args.get("channel")
        identifier = request.args.get("id")

    is_authenticated = check_token(request.headers, session)

    if not is_authenticated:
        return abort(403)

    if not action:
        return jsonify({"error": "No action specified."}), 400

    print(action)

    if request.method == "GET":
        return process_get_request(request, action, identifier, channel)
    elif request.method == "POST":
        return process_post_request(request, action, method)

    return (
        jsonify(
            {
                "error": "invalid_request",
                "error_description": "The action and method provided are not valid.",
            }
        ),
        400,
    )


if __name__ == "__main__":
    main.run()
