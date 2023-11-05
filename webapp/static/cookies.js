// cookies.js
window.addEventListener('load', function () {
    let popup = document.getElementById("cookie-popup");
    let acceptedCookies = localStorage.getItem('acceptedCookies');
    if (!acceptedCookies) {
        popup.style.display = "block";
    }

    document.getElementById("accept-cookies").addEventListener('click', function() {
        localStorage.setItem('acceptedCookies', 'true');
        popup.style.display = "none";
    });
});