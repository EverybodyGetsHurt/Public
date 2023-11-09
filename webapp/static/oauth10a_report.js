document.addEventListener("DOMContentLoaded", function() {
    // Get the form element
    var form = document.querySelector("#impersonated-channel-form");
    
    // Get the error section
    var errorSection = document.querySelector(".error-section");
    
    // Add a submit event listener to the form
    form.addEventListener("submit", function(event) {
        // Prevent the form from submitting normally
        event.preventDefault();
        
        // Get the selected option from the form
        var select = form.querySelector("select");
        var option = select.options[select.selectedIndex];
        var value = option.value;

        // Validate selected value
        if (!value) {
            errorSection.textContent = "Please select a channel.";
            return;
        }

        // Set the URL of the iframe to the endpoint that returns the JSON response
        var url = "{{ url_for('oauth10areport.oauth10areportimpersonators') }}";
        url += "?impersonated_channel=" + encodeURIComponent(value);
        var iframe = document.getElementById("response-frame");
        iframe.src = url;
        iframe.style.height = "400px"; // Reset the height to the minimum value
    });

    // Add a message event listener to the iframe
    var iframe = document.getElementById("response-frame");
    iframe.addEventListener("load", function() {
        try {
            // Parse the JSON response and display it in the iframe
            var response = JSON.parse(iframe.contentWindow.document.body.innerHTML);
            var pre = document.createElement("pre");
            pre.textContent = JSON.stringify(response, null, 2);
            iframe.contentWindow.document.body.innerHTML = "";
            iframe.contentWindow.document.body.appendChild(pre);

            // Set the height of the iframe to match the content
            var newHeight = pre.offsetHeight + 20; // Add some extra padding
            iframe.style.height = newHeight + "px";
        } catch (error) {
            errorSection.textContent = "An error occurred while processing the response.";
        }
    });
});
