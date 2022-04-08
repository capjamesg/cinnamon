var char_count = 0;
var last_char = null;
var xhr = new XMLHttpRequest();
var all_uploaded_photos = "";

xhr.open('GET', '/static/emojis.json');

xhr.send();
var emoji_names = [];
var emojis = [];
var showing_person_tags = [];
var showing_hash_tags = [];

var is_private = false;

function hide_all_forms() {
    var forms = ["#rating_form", "#rsvp_form", "#gif_search_bar", "#reply_to"];
    for (var i = 0; i < forms.length; i++) {
        // hide each form
        var form_item = document.querySelector(forms[i]);
        form_item.style.display = "none";
    }
}

xhr.onload = function() {
    if (xhr.status === 200) {
        emoji_req = JSON.parse(xhr.responseText);
        // split json into two lists
        for (var i in emoji_req) {
            emojis.push(i);
            emoji_names.push(emoji_req[i]);
        }
    }
};

var form = document.getElementById("content");

function establish_focus() {
    // the following three lines of code ensures focus is preserved at the end of the line
    // the code was taken from https://stackoverflow.com/questions/1125292/how-to-move-cursor-to-end-of-contenteditable-entity
    // specifically, Juank's comment
    form.focus();
    // select all the content in the element
    document.execCommand('selectAll', false, null);
    // collapse selection to the end
    document.getSelection().collapseToEnd();
}

var character_count_element = document.getElementById("character_count");

form.onkeydown = function(e) {
    character_count_element.innerHTML = form.innerText.replace("<br>", "").length;
}

var post_image = document.getElementById("post_image");

post_image.addEventListener("change", function() {
    var file = this.files[0];
    uploadFile(file);
});

// draggable code derived from https://www.smashingmagazine.com/2018/01/drag-drop-file-uploader-vanilla-js/
;
['dragenter', 'dragover', 'dragleave', 'drop'].forEach(eventName => {
    form.addEventListener(eventName, preventDefaults, false)
})

function preventDefaults(e) {
    e.preventDefault()
    e.stopPropagation()
}

form.addEventListener('dragover', handleDragOver)
form.addEventListener('dragleave', handleDragLeave)

function handleDragOver(e) {
    e.preventDefault()
    e.stopPropagation()

    var data_message = document.getElementById("data_message");

    data_message.innerHTML = "Drop an image into the box above to upload it to your site.";
    data_message.className = "data_message";

    form.after(data_message);

    form.classList.add('dragover')
}

var is_writing_contact = false;
var is_writing_hashtag = false;

var all_images = "";
var showing_emojis = [];

function insert_into_editor(text, identifier) {
    // delete all text after last identifier sign
    var last_position = form.innerHTML.lastIndexOf(identifier);

    console.log(form.innerHTML.substring(0, last_position))

    form.innerHTML = form.innerHTML.substring(0, last_position);
    if (identifier == "!") {
        form.innerHTML += text;
    } else {
        form.innerHTML += identifier + text;
    }
    form.innerHTML = form.innerHTML.replace("<br>", "");

    document.getElementById("data_message").style.display = "none";

    if (document.getElementById("in_editor_tooltip")) {
        document.getElementById("in_editor_tooltip").style.display = "none";
    }

    establish_focus()

    if (identifier == "@") {
        showing_person_tags = [];
    } else if (identifier == "#") {
        showing_hash_tags = [];
    } else if (identifier == "!") {
        showing_emojis = [];
    }

    last_char = null;
}

var gif_search_box = document.getElementById("gif_search_bar");

gif_search_box.addEventListener("keyup", function(e) {
    if (e.keyCode === 32) {
        add_gif();
    }
});

function add_gif() {
    var gif_api_url = "https://api.gfycat.com/v1/gfycats/search?search_text=" + gif_search_box.value;

    fetch(gif_api_url)
        .then(function(response) {
            return response.json();
        }).then(function(data) {
            var gifs = data.gfycats.slice(0, 10);
            var gif_list = document.getElementById("gif_list");
            // turn list into a flex item
            gif_list.style.display = "flex";
            gif_list.style.flexWrap = "wrap";
            gif_list.innerHTML = "";
            for (var i = 0; i < gifs.length; i++) {
                var gif_item = document.createElement("div");
                gif_item.className = "gif_item";
                gif_item.innerHTML = "<img src='" + gifs[i].gif100px + "' style='margin-left: 20px; width: 100px;'>";
                gif_item.onclick = function() {
                    var gif_url = this.querySelector("img").src;
                    form.innerHTML += "<img src='" + gif_url + "'>";
                    document.getElementById("data_message").style.display = "none";
                    gif_list.innerHTML = "";
                    // hide search box
                    gif_search_box.style.display = "none";
                    establish_focus();
                }
                gif_list.appendChild(gif_item);
            }
        });
}

// listen for @ in form
form.addEventListener("keydown", function(e) {
    var data_message = document.getElementById("data_message");
    data_message.style.textAlign = "left";

    // if keycode is #
    if (e.keyCode == 51) {
        is_writing_hashtag = true;
        is_writing_contact = false;

        // show data_message
        data_message.style.display = "block";
    }

    if (e.keyCode == 50) {
        is_writing_contact = true;
        is_writing_hashtag = false;

        // show data_message
        data_message.style.display = "block";
    }

    // if :) or :D in form
    if (form.innerHTML.includes(":)")) {
        is_writing_contact = false;
        is_writing_hashtag = false;

        form.innerHTML = form.innerHTML.replace(":)", "🙂");
    } else if (form.innerHTML.includes(":D")) {
        is_writing_contact = false;
        is_writing_hashtag = false;

        form.innerHTML = form.innerHTML.replace(":D", "😂");
    }

    if (e.keyCode == 32) {
        // remove all brs
        form.innerHTML = form.innerHTML.replace(/<br>/g, "");
        if (is_writing_hashtag) {
            // get last hashtag and make it blue
            var hashtag = form.innerHTML.split("#")[form.innerHTML.split("#").length - 1];

            form.innerHTML = form.innerHTML.replace("#" + hashtag, "<span style='color:blue'>#" + hashtag + "</span> ");
        }

        if (is_writing_contact) {
            // get last contact and make it blue
            var contact = form.innerHTML.split("@")[form.innerHTML.split("@").length - 1];

            form.innerHTML = form.innerHTML.replace("@" + contact, "<span style='color:blue'>@" + contact + "</span> ");
        }

        // if last word started with http:// or https:// and . in url
        if (form.innerHTML.split(" ")[form.innerHTML.split(" ").length - 1].split(".")[0].split("http://").length > 1 ||
            form.innerHTML.split(" ")[form.innerHTML.split(" ").length - 1].split(".")[0].split("https://").length > 1) {
            // get last word and make it blue
            var url = form.innerHTML.split(" http")[-1];

            // get index of url
            var url_index = form.innerHTML.lastIndexOf(url);
            var previous_char = form.innerHTML.substring(url_index - 1, url_index);

            if (previous_char != '"') {
                form.innerHTML = form.innerHTML.replace(url, "<span style='color:blue'>" + url + "</span> ");
            } else {
                form.innerHTML = form.innerHTML.replace(url, "<span style='color:blue'>" + url + "</span> ");

                // make http request to get context
                fetch("/context", {
                    method: "POST",
                    headers: {
                        "Content-Type": "application/json"
                    },
                    body: JSON.stringify({
                        url: url
                    })
                }).then(function(response) {
                    return response.json();
                }).then(function(data) {
                    var context_box = document.createElement("div");

                    all_images += `<img src="${data.image} alt="Featured image" />`;

                    context_box.className = "context_box";

                    context_box.innerHTML = `
                    <a href="${data.url}" target="_blank">
                        <img src="${data.image} alt="Featured image" />
                        <h4>${data.author.name}</h4>
                        <p>${data.content.html}</p>
                    </a>
                    `;

                    form.append(context_box);
                });
            }
        }
        establish_focus();

        is_writing_contact = false;
        is_writing_hashtag = false;

        data_message.innerHTML = "";
        data_message.classList.remove("data_message");
    }

    if (is_writing_hashtag) {
        editor_substitution("#", hashtags, []);
    }

    if (is_writing_contact) {
        editor_substitution("@", names, people_tags);
    }

    if (!is_writing_contact && !is_writing_hashtag) {
        var data_message = document.getElementById("data_message");

        data_message.innerHTML = "";

        form.after(data_message);
    }

    if (is_writing_contact && e.keyCode == 9) {
        e.preventDefault();

        // get first person tag
        var first_person_tag = showing_person_tags[0];

        insert_into_editor(first_person_tag.username, "@");
    } else if (is_writing_hashtag && e.keyCode == 9) {
        e.preventDefault();

        // get first hashtag
        var first_hashtag = showing_hash_tags[0];

        insert_into_editor(first_hashtag, "#");
    } else if (last_char == 49 && e.keyCode == 9) {
        e.preventDefault();

        // get first hashtag
        var first_emoji = showing_emojis[0];

        insert_into_editor(first_emoji, "!");
    }

    if (e.keyCode == 49) {
        last_char = 49;
    } else if (e.keyCode == 221) {
        last_char = e.keyCode;
    }

    if (last_char == 49) {
        editor_substitution("!", emoji_names, emojis);

        if (e.keyCode == 32 && !is_writing_hashtag && !is_writing_contact) {
            // if value in emoji
            // get last index of :
            var last_index = form.innerHTML.lastIndexOf("!");
            // get substring from last index to end
            var user_emoji_name = form.innerHTML.substring(last_index + 1);

            var valid_emojis_to_show = emoji_names.map(function(emoji_name, index) {
                if (emoji_name.startsWith(user_emoji_name)) {
                    return emojis[index];
                }
            });

            valid_emojis_to_show = valid_emojis_to_show.filter(item => item != undefined);

            var exact_match = valid_emojis_to_show.filter(item => item == user_emoji_name);

            if (exact_match.length == 1) {
                form.innerHTML = form.innerHTML += exact_match[0];
                form.innerHTML = form.innerHTML.replace("!" + exact_match, "");
                var possible_emojis = document.getElementById("data_message");
                possible_emojis.innerHTML = "";
            }

            if (valid_emojis_to_show.length > 0) {
                form.innerHTML = form.innerHTML += valid_emojis_to_show[0];
                form.innerHTML = form.innerHTML.replace("!" + user_emoji_name, "");
                var possible_emojis = document.getElementById("data_message");
                possible_emojis.innerHTML = "";
            }
        }
    } else if (last_char == 221) {
        var last_index = form.innerHTML.lastIndexOf("[]");
        // get substring from last index to end
        var link = form.innerHTML.substring(last_index + 2, form.innerHTML.length);

        if (e.keyCode == 32 && !is_writing_hashtag && !is_writing_contact) {
            form.innerHTML = form.innerHTML.replace("[]" + link, "<a href='https://" + link + "'>" + link + "</a>");
        }
    } else if (last_char == 32) {
        last_char = null;
    }
});

function opaqueImage(image_url) {
    var image = document.getElementById(image_url);
    image.style.opacity = "0.5";
}

function removeOpaqueImageStyle(image_url) {
    var image = document.getElementById(image_url);
    image.style.opacity = "1";
}

function removeImage(image_url) {
    var image = document.getElementById(image_url);
    image.remove();
    all_uploaded_photos = all_uploaded_photos.replace("<img class='u-photo' src='" + image_url + "' alt='' />", "");
}

function handleDragLeave(e) {
    e.preventDefault()
    e.stopPropagation()

    var data_message = document.getElementById("data_message");

    data_message.innerHTML = "";
    data_message.classList = "";

    form.classList.remove('dragover')
}

form.addEventListener('drop', handleDrop, false)

function handleDrop(e) {
    let dt = e.dataTransfer
    let files = dt.files

    handleFiles(files)
    handleDragLeave(e)
}

function handleFiles(files) {
    ([...files]).forEach(uploadFile)
}

function uploadFile(file) {
    let formData = new FormData()

    formData.append('file', file)

    fetch("/media", {
            method: 'POST',
            body: formData
        })
        .then(response => response.json())
        .then(function(response) {
            var photos = document.getElementById("photos");

            var url = response["result"];

            var new_photo = document.createElement("img");
            new_photo.classList = "u-photo";
            new_photo.src = url;
            new_photo.id = url;
            new_photo.setAttribute("onclick", "removeImage('" + url + "')");
            new_photo.setAttribute("onmouseover", "opaqueImage('" + url + "')");
            new_photo.setAttribute("onmouseout", "removeOpaqueImageStyle('" + url + "')");

            all_uploaded_photos += "<img class='u-photo' src='" + url + "' alt='' />";

            // add image
            photos.appendChild(new_photo);

            send_notification("<p>Your photo was successfully uploaded.</p>")
        })
        .catch(() => {
            send_notification("<p>Your photo could not be uploaded.</p>")
        })
}