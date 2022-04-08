var js_req = document.getElementsByClassName("js");

for (var i = 0; i < js_req.length; i++) {
    js_req[i].style.display = "inline";
}

function trigger_modal(id, is_editor_box = false) {
    var modal = document.getElementById(id);
    if (id == "private") {
        is_private = !is_private;
    }
    if (modal.style.display == "none") {
        if (is_editor_box) {
            hide_all_forms();
        }
        modal.style.display = "block";
    } else {
        modal.style.display = "none";
        if (is_editor_box) {
            hide_all_forms();
        }
    }
}

function close_modal(event) {
    var modal = document.getElementsByClassName("modal");
    for (var i = 0; i < modal.length; i++) {
        if (event.target == modal[i]) {
            modal[i].style.display = "none";
        }
    }
}

function show_video(url, id) {
    var iframe = document.createElement("iframe");
    iframe.src = url;
    iframe.width = "640";
    iframe.height = "480";
    iframe.frameborder = "0";
    iframe.allowfullscreen = "true";
    iframe.style.display = "block";
    var to_replace = document.getElementById(id);
    to_replace.parentNode.replaceChild(iframe, to_replace);
}

// replace urls on all embedded videos
var all_videos = document.getElementsByClassName("embedded_video");

for (var i = 0; i < all_videos.length; i++) {
    var id = all_videos[i].id;
    all_videos[i].href = "#" + id + "-heading";
}

var all_reaction_links = document.getElementsByClassName("reaction");

for (var i = 0; i < all_reaction_links.length; i++) {
    var id = all_reaction_links[i].id;
    all_reaction_links[i].href = "#";
}

function submit_micropub(id, url) {
    var form = document.getElementById(id + "-form");
    fetch('/react?is_reply=true', {
        method: 'POST',
        body: new URLSearchParams({
            "h": "entry",
            "in-reply-to": url,
            "content": form.value,
            "uid": id,
            "private": is_private
        })
    }).then(function(response) {
        if (response.ok) {
            send_notification("Your reply has been sent.");
        } else {
            send_notification("There was an error sending your reply.");
        }
        trigger_modal(id + "-textbox");
    });
}

function send_notification(notification_text) {
    var notification = document.createElement("section");
    var body = document.getElementsByTagName("body")[0];
    notification.className = "notification_bar";
    notification.innerHTML = "<p>" + notification_text + "";
    // add notification to top of body
    body.insertBefore(notification, body.firstChild);

    setTimeout(function() {
        body.removeChild(notification);
    }, 5000);
}

function post_note(all_uploaded_photos) {
    // send form-encoded response to micropub endpoint
    var form = document.getElementById("content");

    var in_reply_to = document.getElementById("reply_to");

    var rsvp = document.getElementById("rsvp");

    var rating = document.getElementById("rating");

    if (form.innerText.length < 10) {
        send_notification("Your note must be at least 10 characters long.");
        return;
    }

    var content = form.innerHTML;

    // remove all html tags that are not p, br, or img
    content = content.replace(/<(?!p|br|img).*?>/g, "");

    content += all_uploaded_photos

    if (in_reply_to.value || rsvp.value || rating.value) {
        var url = "/react?is_reply=true"

        if (rsvp) {
            content += '<span class="p-rsvp">' + rsvp.value + '</span> ';
        }

        if (rating) {
            content += '<span class="p-rating">' + rating.value + '</span> ';
        }

        var post_body = new URLSearchParams({
            "h": "entry",
            "in-reply-to": in_reply_to.value,
            "content": content,
            "uid": in_reply_to.value,
            "private": is_private
        });
    } else {
        var url = "/react?is_reply=note";

        var post_body = new URLSearchParams({
            "h": "entry",
            "content": content,
            "private": is_private
        })
    }

    fetch(url, {
        method: 'POST',
        body: post_body,
    }).then(function(response) {
        if (response.ok) {
            send_notification("Your post has been created.");
            form.value = "";
        } else {
            send_notification("There was an error sending your reply.");
        }
    });
}

function send_reaction(reaction, reaction_name, post_url, post_id) {
    fetch('/react', {
        method: 'POST',
        body: new URLSearchParams({
            "h": "entry",
            "reaction": reaction,
            "url": post_url,
            "uid": post_id
        })
    }).then(function(response) {
        // if status code == 200
        if (response.status == 200) {
            send_notification("Your " + reaction_name + " has been sent.");
        }
        var reaction_link = document.getElementById(post_id + "-" + reaction);
        reaction_link.classList.add("reacted");
    })
}

function send_unfollow(url, id) {
    fetch('/unfollow', {
        method: 'POST',
        body: new URLSearchParams({
            "channel": id,
            "url": url
        })
    }).then(function(response) {
        // if status code == 200
        if (response.status == 200) {
            send_notification("You have unfollowed the feed.");
        }
        var list_item = document.getElementById(id);

        list_item.parentNode.removeChild(list_item);
    })
}

function editor_substitution(substitution_character, mapping_list, list_items = []) {
    var data_message = document.getElementById("data_message");

    data_message.classList.remove("data_message");

    var last_index = form.innerHTML.lastIndexOf(substitution_character);
    // get substring from last index to end
    var user_input = form.innerHTML.substring(last_index + 1).replace("<br>", "");

    var to_show = [];

    if (user_input.length + 1 > 1) {
        mapping_list.map(function(item, index) {
            if (item.startsWith(user_input)) {
                if (substitution_character == "@") {
                    var to_add = people_tags[item.toLowerCase()];

                    to_add["username"] = item;

                    to_show.push(to_add);
                } else if (substitution_character == "#") {
                    to_show.push(item);
                } else if (substitution_character == "!") {
                    var name_item = list_items[index];
                    to_show.push(item + " (" + name_item + ")")
                }
            }
        });

        var valid_to_show = to_show.filter(item => item != undefined);

        // get first five to show
        var to_show_5 = valid_to_show.slice(0, 5);

        data_message.style.textAlign = "left";

        var main_html = "<ul id='in_editor_tooltip'>";

        for (var i in to_show_5) {
            if (substitution_character == "!") {
                showing_emojis = to_show_5.map(item => item.split(" ")[1].replace("(", "").replace(")", ""));
                main_html += `
                    <li>
                        <a href="#" onclick="insert_into_editor('${to_show_5[i].split(" ").slice(1).join(" ")}', '!')">
                            ${to_show_5[i]}
                        </a>
                    </li>
                `;
            } else if (substitution_character == "#") {
                showing_hash_tags = to_show_5;
                main_html += `
                    <li>
                        <a href="#" onclick="insert_into_editor('${to_show_5[i]}', '#')">
                            #${to_show_5[i]}
                        </a>
                    </li>
                `;
            } else if (substitution_character == "@") {
                showing_person_tags = to_show_5;
                main_html += `
                    <li>
                        <a onclick="insert_into_editor('${to_show_5[i]["username"]}', '@')">
                            <p>
                                ${to_show_5[i].favicon ? `<img src="${to_show_5[i].favicon}" alt="${to_show_5[i].username}'s profile image" style='height: 50px; width: 50px' />` : ""}
                                ${to_show_5[i].full_name} (${to_show_5[i].username})
                            </p>
                        </a>
                    </li>
                `;
            }
        }

        main_html += "</ul>";
        data_message.innerHTML = main_html;
        data_message.classList.add("data_message_scroll");

        // display: block
        data_message.style.display = "block";

        form.after(data_message);
    }
}