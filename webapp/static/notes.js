document.querySelectorAll('.close').forEach(function(button) {
    button.addEventListener('click', function(event) {
        deleteNote(event.target.dataset.noteId);
    });
});
