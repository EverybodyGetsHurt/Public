// index.js

// Define the intended domain
const intendedDomain = "lifelessandcalm.com";

// Function to get the correct start URL based on the domain
function getStartUrl() {
    const currentDomain = window.location.hostname;
    if (currentDomain === intendedDomain) {
        return null;
    } else {
        return "https://" + intendedDomain;
    }
}

// Redirect to the correct start URL if the domain is not the intended one
const startUrl = getStartUrl();
if (startUrl && window.location.href !== startUrl) {
    window.location.href = startUrl;
}
