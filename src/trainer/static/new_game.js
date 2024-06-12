$('.choose-color').on('click', function () {
  let color = $(this).attr('id');
  (color);
  $.post("/choose_color", { color: color }, function (data) {
    if (data.response == 'success') {
      window.location = data.redirect;
    }
  });
});