var js_req = document.getElementsByClassName("js");

for (var i = 0; i < js_req.length; i++) {
    js_req[i].style.display = "inline";
}

function trigger_modal(id) {
    var modal = document.getElementById(id);
    if (modal.style.display == "none") {
        modal.style.display = "block";
    } else {
        modal.style.display = "none";
    }
}

function close_modal() {
    var modal = document.getElementsByClassName("modal");
    for (var i = 0; i < modal.length; i++) {
        if (event.target == modal[i]) {
            modal[i].style.display = "none";
        }
    }
}

window.onclick = function(event) {
    event.preventDefault();
    close_modal()
}

function show_channels() {
    var channels = document.getElementById("sidebar");

    if (channels.style.display == "none") {
        channels.style.display = "block";
    } else {
        channels.style.display = "none";
    }
}

function show_settings() {
    var settings = document.getElementById("settings");

    if (settings.style.display == "none") {
        settings.style.display = "block";
    } else {
        settings.style.display = "none";
    }
}

function show_all(id) {
    var item_to_show = document.getElementById(id + "-full");
    var show_label = document.getElementById(id + "-show");
    var original_text = document.getElementById(id + "-start");

    if (item_to_show.style.display === "none") {
        item_to_show.style.display = "inline";
        show_label.innerHTML = "Show less";

        original_text.innerHTML = original_text.innerHTML.replace("...", "");
    } else {
        item_to_show.style.display = "none";
        show_label.innerHTML = "Show more";

        original_text.innerHTML = original_text.innerHTML + " ...";
    }
}
var search_button = document.getElementById("search_button");
var subscribe_to_feed = document.getElementById("subscribe_to_feed");
var channel_settings_button = document.getElementById("channel_settings_button");

search_button.href = "#";
subscribe_to_feed.href = "#";
channel_settings_button.href = "#";

search_button.onclick = function(event) {
    event.preventDefault();
    trigger_modal("search");
}

subscribe_to_feed.onclick = function(event) {
    event.preventDefault();
    trigger_modal("subscribe");
}

channel_settings_button.onclick = function(event) {
    event.preventDefault();
    trigger_modal("channel_settings");
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