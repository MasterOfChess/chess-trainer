$('.choose-color').on('click', function () {
  let color = $(this).attr('id');
  console.log(color);
  $.post("/choose_color", { color: color }, function (data) {
    if (data.response == 'success') {
      window.location = data.redirect;
    }
  });
});