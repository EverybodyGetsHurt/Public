function deleteNote(noteId) {
    console.log("deleteNote called with noteId:", noteId);
    fetch("/deletenote", {
        method: "POST",
        body: JSON.stringify({noteId: noteId}),
    }).then((_res) => {
        console.log('Note deleted');
        // window.location.href = "/";
    });
}