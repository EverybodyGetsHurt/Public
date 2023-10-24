// GDPRrrrAAHrRRhHrAaahrrrrr.js

document.addEventListener('DOMContentLoaded', function () {
  const gdprPopup = document.getElementById('gdpr-popup');
  const gdprAcceptButton = document.getElementById('gdpr-accept');

  function setCookie(name, value, days) {
    const date = new Date();
    date.setTime(date.getTime() + days * 24 * 60 * 60 * 1000);
    const expires = '; expires=' + date.toUTCString();
    document.cookie = name + '=' + value + expires + '; path=/';
  }

  function getCookie(name) {
    const nameEQ = name + '=';
    const cookies = document.cookie.split(';');
    for (let i = 0; i < cookies.length; i++) {
      let cookie = cookies[i];
      while (cookie.charAt(0) == ' ') cookie = cookie.substring(1, cookie.length);
      if (cookie.indexOf(nameEQ) == 0) return cookie.substring(nameEQ.length, cookie.length);
    }
    return null;
  }

  function checkConsent() {
    if (!getCookie('ChewbaccaTheCookie')) {
      gdprPopup.style.display = 'block';
    }
  }

  gdprAcceptButton.addEventListener('click', function () {
    setCookie('ChewbaccaTheCookie', 'accepted', 365);
    gdprPopup.style.display = 'none';
  });

  checkConsent();
});
