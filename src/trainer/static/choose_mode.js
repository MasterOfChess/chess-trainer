$('.choose-color').on('click', function () {
  let mode = $(this).attr('id');
  console.log(mode);
  $.post("/choose_mode", { mode: mode }, function (data) {
    if (data.response == 'success') {
      window.location = data.redirect;
    }
    if (data.response == 'error') {
      window.location = data.redirect
    }
  });
});