var current_page = 0;
var page_switcher = document.createElement("div");
var ispaginated = false;

$(document).ready(function(){
    $(".item_link").removeAttr("href");
    var cells = $(".item_cell");
    var pages = $(".backpack-page").not("#page-0");
    var hashpart = document.location.hash;
    var thepage = hashpart.substring(6) - 1;

    if (pages.length > 0) {
        page_switcher.id = "page-switcher";
        page_switcher.innerHTML = '<div class="button" id="prev-button">&lt; Previous</div><span id="page-counter">' +
            '</span><div class="button" id="next-button">Next &gt;</div>';
        $(page_switcher).appendTo("#backpack");
        $("#next-button, #prev-button").click(backpack_page_switch);
        $(page_switcher).hide();
    }

    if (thepage >= 0 || (get_cookie("pagination") == 1 && pages.length > 0)) {
        var backpack = $("#backpack");

        if (thepage < 0) {
            thepage = 0;
        }

        if (pages[thepage] != undefined) {
            current_page = thepage;
            backpack_mode_paginated(pages);
        }
    }
    var pagination_toggler = document.createElement("div");
    if (ispaginated) {
        pagination_toggler.innerHTML = "Show All";
    } else {
        pagination_toggler.innerHTML = "Show Pages";
    }
    $(pagination_toggler).addClass("button");
    $(pagination_toggler).appendTo("#option-controls");
    $(pagination_toggler).click(function(){
        if (ispaginated) {
            set_cookie("pagination", 0);
            backpack_mode_full(pages);
            pagination_toggler.innerHTML = "Show Pages";
        } else {
            set_cookie("pagination", 1);
            backpack_mode_paginated(pages);
            pagination_toggler.innerHTML = "Show All";
        }
    });

    cells.hover(function() {
        var attribs = $(this).find(".item_attribs");
        attribs.show();
        if (attribs.length) {
            var scrollh = $(document).scrollTop();
            /* When a browser supports something simple yet non-standard like
               window.innerHeight, IE has to be ULTRA non-standard.
            */
            var windowh = document.documentElement.clientHeight;
            var offsety = attribs.offset().top;
            var threshold = (scrollh + windowh);
            var posbottom = (offsety + attribs.height());
            if (this.deftop == undefined) {
                this.deftop = attribs.css("top");
            }

            if (posbottom > threshold) {
                attribs.css("top", (-attribs.height() - 17) + "px");
            } else {
                attribs.css("top", this.deftop);
            }
        }
    }, function() {
        var attribs = $(this).find(".item_attribs");
        attribs.css("top", this.deftop);
        attribs.hide();
    });

    $(document).scroll(function() {
        $(".item_attribs").hide();
    });

    cells.click(function() {
        item_open(this.id.slice(1));
    });

    $(".item-image").one("error", function() {
        this.src = virtual_root + "static/item_icons/Invalid_icon.png";
    });
});

function item_image_resize(img, iw, ih, w, h) {
    var ratio = Math.min(w / iw, h / ih);

    img.width(ratio * iw);
    img.height(ratio * ih);
}

function item_resize_event(event, ui) {
    var item = $(event.target);
    var image = item.find(".item-image");

    if (ui.size == undefined) {
        ui.size = {"height":  item.height(),
                   "width": item.width()};
    }

    item_image_resize(image, image.width(), image.height(),
                      Math.min(ui.size.width - 200, 512),
                      Math.min(ui.size.height - 100, 512));

    item.height(ui.size.height);
    item.width(image.width() + item.find("#item_attrs").width() + 50);
    item.find("#stat_vertrule").height(ui.size.height);
}

function item_open_success(data, status, xhr) {
    var page = $(data);
    var dialog_title = page.filter("#header").find("h1");
    var dialog_content = page.filter("#content").find("#item_stats");
    var dialog_width = 850;
    var dialog_height = 670;
    var item_id = dialog_content.find("#item_id").html();

    dialog_content.find("#item_attrs").append("<br/><br/><a href=\"" + virtual_root + "item/" + item_id + "\">Link to this item</a>");
    dialog_title.css({"font-size": "1.6em", "margin": "0", "padding": "0"});

    if ($(window).height() < dialog_height) {
        dialog_height = $(window).height();
    }
    if ($(window).width() < dialog_width) {
        dialog_width = $(window).width();
    }

    $("#loading_" + item_id).remove();

    $(dialog_content).dialog({
        resize: item_resize_event,
        open: item_resize_event,
        title: dialog_title,
        width: dialog_width,
        height: dialog_height,
        minWidth: 250,
        minHeight: 200,
        modal: true
    });
}

function item_open(item_id) {
    var item_url = virtual_root + "item/" + item_id;
    var loading_id = "loading_" + item_id;
    var cell_id = $("#s" + item_id);
    if (cell_id.find("#" + loading_id).length > 0) {
        return;
    }
    cell_id.prepend("<div id=\"" + loading_id + "\"><b>Loading...</b></div>");
    var oldcontent = $("body").find(".dedicated_item");
    var reallyoldcontent = null;
    for (var i = 0; i < oldcontent.length; i++) {
        var id = $(oldcontent[i]).find("#item_id").html();
        if (id == item_id) {
            reallyoldcontent = oldcontent[i];
            break;
        }
    }

    if (reallyoldcontent) {
        $(reallyoldcontent).dialog({open: function(e, u) { $("#" + loading_id).remove(); }});
    } else {
        $.get(item_url, item_open_success, {}, "html");
    }
}

function autocomplete_magic(req, resp) {
  var finalcomp = new Array ();
  $.getJSON (virtual_root + "comp/" + req.term, function (data, status) {
      for (var i = 0; i < data.length; i++) {
          itemdata = data[i]
          itemlabel = itemdata["persona"];
          if (itemdata["id_type"] == "id") {
              itemlabel += " (" + itemdata["id"] + ')';
          }
          finalcomp.push({label: itemlabel, value: itemdata["id"]});
      }

      resp (finalcomp.slice (0, 20));
  });
}

function autocomplete_attach(uid) {
    $("#user").autocomplete({
        minLength: 2,
        source: autocomplete_magic
    });
}

function backpack_page_switch() {
    var bp = $("#backpack");
    var packs = $(".backpack-page").not("#page-0");
    var newpage;

    if (this.id == "prev-button") {
        newpage = current_page - 1;
    } else {
        newpage = current_page + 1;
    }

    if (newpage < 0 || (newpage + 1) > packs.length) {
        return;
    }

    $(packs).hide();
    current_page = newpage;
    $(packs[current_page]).show();

    document.location.hash = '#page-' + (current_page + 1);
    $("#page-counter")[0].innerHTML = (current_page + 1) + '/' + packs.length;
}

function backpack_mode_paginated(pages) {
    $("#page-counter")[0].innerHTML = (current_page + 1) + '/' + pages.length;
    pages.hide();
    $(pages[current_page]).show();
    $(page_switcher).show();
    ispaginated = true;
}

function backpack_mode_full(pages) {
    pages.show();
    $(page_switcher).hide();
    ispaginated = false;
}

function delete_cookie(cookie) {
    document.cookie = cookie + "=0; expires=Thu Feb 17 2011 08:33:55 GMT-0700 (MST);";
}

function get_cookie(cookie) {
    cookies = document.cookie.split(';');
    for (i = 0; i < cookies.length; i++) {
        thecookie = cookies[i];
        cookiename = $.trim(thecookie.substr(0, thecookie.indexOf('=')));
        cookievalue = $.trim(thecookie.substr(thecookie.indexOf('=') + 1));

        if (cookiename == cookie) {
            return cookievalue;
        }
    }
}

function set_cookie(cookie, val) {
    document.cookie = cookie + "=" + val;
}
