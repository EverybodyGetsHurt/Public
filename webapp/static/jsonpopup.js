const cspNonce = document.querySelector("[nonce]").nonce;
      document.addEventListener("DOMContentLoaded", () => {
        // Loop through all delete buttons and add event listener to each of them
        document.querySelectorAll('[id^="deleteBtn"]').forEach(deleteBtn => {
          deleteBtn.addEventListener("click", () => {
            // Extract the note ID from the delete button ID
            const noteId = deleteBtn.id.replace("deleteBtn", "");
            // Send a POST request to delete the note
            fetch("/delete-note", {
              method: "POST",
              headers: {
                "Content-Type": "application/json",
              },
              body: JSON.stringify({ noteId: noteId }),
            }).then(() => {
              // Reload the page to update the note list
              window.location.reload();
            });
          });
        });
      });