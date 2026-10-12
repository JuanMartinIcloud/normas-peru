(function ($) {
    $(document).ready(function () {
        space_StatusDolar
        $("#space_StatusDolar").trigger("submit");
        $("#space_PublicacionesdelDia").trigger("submit");
        $("#space_PublicacionesTupaDia").trigger("submit");
        $("#space_SumarioNormas").trigger("submit");
        $("#space_NormasPublicadas").trigger("submit");
        $("#space_AndinaNoticias").trigger("submit");
        $("#space_EdicionImpresa").trigger("submit");

        $("nav").menumaker({
            title: "MENU",
            format: "multitoggle"

        });

        $(window).scroll(function () {
            if ($(this).scrollTop() > 50) {
                $('nav').addClass("fixed").fadeIn();
                $('#logomin').empty();
                $('#logomin').prepend('<img src="../../img/logomin.png"  alt="#">');
            }
            else {
                $('#logomin').empty();
                $('nav').removeClass("fixed");
            }
        });

        $(function () {
            // this will get the full URL at the address bar
            var url = window.location.href;

            // passes on every "a" tag 
            $("#mimenu a").each(function () {
                // checks if its the same on the address bar
                if (url == (this.href)) {
                    $(this).closest("li").addClass("active");
                }
            });
        });

    });
})(jQuery);


(function ($) {

  $.fn.menumaker = function (options) {

        var nav = $(this), settings = $.extend({
            title: "Menu",
            format: "dropdown",
            sticky: false
        }, options);

        return this.each(function () {
            nav.prepend('<div id="menu-button">' + settings.title + '</div>');
            $(this).find("#menu-button").on('click', function () {
                $(this).toggleClass('menu-opened');
                var mainmenu = $(this).next('ul');
                if (mainmenu.hasClass('open')) {
                    mainmenu.hide().removeClass('open');
                }
                else {
                    mainmenu.show().addClass('open');
                    if (settings.format === "dropdown") {
                        mainmenu.find('ul').show();
                    }
                }
            });

            nav.find('li ul').parent().addClass('has-sub');

            multiTg = function () {
                nav.find(".has-sub").prepend('<span class="submenu-button"></span>');
                nav.find('.submenu-button').on('click', function () {
                    $(this).toggleClass('submenu-opened');
                    if ($(this).siblings('ul').hasClass('open')) {
                        $(this).siblings('ul').removeClass('open').hide();
                    }
                    else {
                        $(this).siblings('ul').addClass('open').show();
                    }
                });
            };

            if (settings.format === 'multitoggle') multiTg();
            else nav.addClass('dropdown');

            if (settings.sticky === true) nav.css('position', 'fixed');
            

            resizeFix = function () {
                if ($(window).width() > 748) {
                    nav.find('ul').show();
                    
                    
                }

                if ($(window).width() <= 748) {
                    nav.find('ul').hide().removeClass('open');
                }
            };
            resizeFix();
            return $(window).on('resize', resizeFix);

        });
    };
})(jQuery);

