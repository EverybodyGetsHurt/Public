"""
The Unauth.py file is responsible for handling the website for users that are anonymous.
This script manages various functionalities intended for users who are not logged into the system,
such as displaying informational pages, managing GDPR consents, and serving essential web files
like security policies and sitemap information.
"""

from flask import Blueprint, render_template, send_from_directory, make_response, request
from flask_login import login_required, current_user

# Blueprint Setup
# ---------------
# Blueprint 'unauth' is defined to group routes associated with unauthenticated users.
# Blueprints in Flask are used to organize a group of related views and other code.
# This makes the application modular, allowing separate features or components
# to be developed and maintained independently.
unauth = Blueprint('unauth', __name__)


# Route Definitions
# -----------------
# The routes defined below handle various functionalities for unauthenticated users.
# They include serving informational pages like 'About' and 'Privacy Policy',
# managing GDPR consents, and serving essential web files for security and SEO.

@login_required
@unauth.route('/', methods=['GET', 'POST'])
@unauth.route('/unauthhome', methods=['GET', 'POST'])
def unauthhome():
    """
    This route serves the home page for unauthorized or public users. The route requires
    authentication, as indicated by the @login_required decorator. It renders the 'unauthhome.html'
    template, providing context variables including the current user, page title, and a
    description about the website's purpose (managing Twitter Impersonators for Crypto Channels).

    Returns:
        - A rendered template 'unauthhome.html' with context variables: user, title, description.
    """
    return render_template(
        "unauthhome.html", user=current_user, title="home", description="Explore Benemortasia.com, a tool to manage "
                                                                        "Twitter Impersonators for our beloved Crypto"
                                                                        " Channels with ease.")


@unauth.route('/unauthabout')
def unauthabout():
    """
    This route is responsible for rendering the 'About' page for unauthorized or public users.

    The function renders the 'unauthabout.html' template. It provides context variables similar to the unauthhome
    function, including the current_user, a title, and a description that narrates the story, mission, and the
    team behind Benemortasia.com.

    Returns:
        - A rendered template 'unauthabout.html' with context variables: user, title, and description.
    """
    return render_template(
        "unauthabout.html", user=current_user, title="about", description="Discover the story of Benemortasia.com, "
                                                                          "our mission, the communities and the "
                                                                          "dedicated team behind it all")


@unauth.route('/gdpr-popup', methods=['GET'])
def gdpr_popup():
    """
    Manages the GDPR consent popup for unauthorized users. It checks for a consent cookie
    ('ChewbaccaTheCookie') and, if consent is already given, returns a confirmation message. Otherwise,
    it renders the GDPR popup template ('GDPRrrrAAHrRRhHrAaahrrrrr.html').

    The function also sets content security policy headers to promote safe content practices and prevent
    cross-site scripting (XSS) attacks.

    Returns:
        - A 200 OK response with message if consent is already given.
        - A rendered GDPR popup template with CSP headers if consent is not already given.
    """
    gdpr_consent = request.cookies.get('ChewbaccaTheCookie')
    if gdpr_consent == 'accepted':
        return make_response('Consent already given.', 200)

    response = make_response(render_template('GDPRrrrAAHrRRhHrAaahrrrrr.html'))
    response.headers['Content-Type'] = 'text/html'
    response.headers['Content-Security-Policy'] = f"default-src 'self' 'nonce-{csp_nonce()}'"
    return response


@unauth.route('/privacy')
def privacy():
    """
    This route serves the Privacy Policy page for unauthorized users. If the user has not previously given GDPR
    consent (determined by the absence of the 'ChewbaccaTheCookie' cookie), the function sets this cookie to
    record their consent.

    The function ensures that the Privacy Policy page is not cached by setting appropriate cache control headers.
    This is important to ensure that users always see the most current version of the policy.

    Returns:
        - A rendered template 'privacy.html' with cache control headers, user context, and additional privacy
          policy information. The response may also include setting a consent cookie if not already set.
    """
    gdpr_consent = request.cookies.get('ChewbaccaTheCookie')
    if gdpr_consent != 'accepted':
        response = make_response(render_template(
            "privacy.html", user=current_user, title="privacy", description="Learn how we protect your "
                                                                            "data at Benemortasia.com by"
                                                                            " reading our detailed "
                                                                            "privacy and security "
                                                                            "policy."))
        response.set_cookie("ChewbaccaTheCookie", value="accepted", secure=True, httponly=True, samesite='Strict')
    else:
        response = make_response(render_template(
            "privacy.html", user=current_user, title="privacy", description="Learn how we protect your data "
                                                                            "at Benemortasia.com by reading "
                                                                            "our detailed privacy and "
                                                                            "security policy."))

    response.headers['Cache-Control'] = 'no-cache, no-store, must-revalidate'
    response.headers['Pragma'] = 'no-cache'
    response.headers['Expires'] = '0'
    return response


# Serving Well-Known Files
# ------------------------
# The routes below are responsible for serving well-known files from a specified directory.
# These files play crucial roles in website security, encryption communication, search engine instructions,
# and SEO optimization. Appropriate MIME type headers are set for each file type to ensure correct interpretation.

# These functions are similar in functionality, serving various well-known files from a specified directory.
# They are important for website security (security.txt), encryption communication (pgp-key.asc),
# search engine instructions (robots.txt), and SEO optimization (sitemap.xml).
# The Content-Type headers are set appropriately for each file type.

# Each of these functions serves a specific file that is important for different aspects of web management:
# - serve_security_txt: Provides the security.txt file, which is a standard for web security policies.
# - serve_pgp_key_asc: Delivers the PGP key file, used for encrypted communication.
# - serve_robots_txt: Serves the robots.txt file, directing web crawlers on how to index the site.
# - serve_sitemap_xml: Delivers the sitemap.xml file, aiding search engines in site indexing for SEO.

# The functions use the `send_from_directory` method to serve these files from a specified directory,
# ensuring that the requests for these files are handled correctly and efficiently.
# They also include appropriate MIME type headers to ensure the files are interpreted correctly by clients.

@unauth.route('/.well-known/security.txt')
def serve_security_txt():
    """
    Serves the 'security.txt' file, a standard for web security policies. This file is critical for
    declaring security policies and contact information related to web security.

    Returns:
        - The 'security.txt' file from the specified directory.
    """
    return send_from_directory('/home/benemortasia/benemortasia/webapp/static/.well-known', 'security.txt')


@unauth.route('/.well-known/pgp-key.asc')
def serve_pgp_key_asc():
    """
    Serves the PGP key file ('pgp-key.asc'), used for encrypted communication. Providing this file
    allows users or other entities to securely communicate using encryption.

    Returns:
        - The 'pgp-key.asc' file from the specified directory.
    """
    return send_from_directory('/home/benemortasia/benemortasia/webapp/static/.well-known', 'pgp-key.asc')


@unauth.route('/robots.txt')
def serve_robots_txt():
    """
    Serves the 'robots.txt' file, providing instructions to web crawlers on how to index the site.
    This is important for SEO and ensures that search engines index the site content appropriately.

    Returns:
        - The 'robots.txt' file with appropriate headers to prevent MIME type sniffing.
    """
    response = send_from_directory('/home/benemortasia/benemortasia/webapp/static/.well-known', 'robots.txt')
    response.headers['Content-Type'] = 'text/plain'
    response.headers['X-Content-Type-Options'] = 'nosniff'
    return response


@unauth.route('/sitemap.xml')
def serve_sitemap_xml():
    """
    Serves the 'sitemap.xml' file, which is crucial for SEO optimization. This file helps search engines
    to more intelligently crawl the site, understanding the site structure and content.

    Returns:
        - The 'sitemap.xml' file with appropriate headers to ensure correct content type.
    """
    response = send_from_directory('/home/benemortasia/benemortasia/webapp/static/.well-known', 'sitemap.xml')
    response.headers['Content-Type'] = 'application/xml'
    response.headers['X-Content-Type-Options'] = 'nosniff'
    return response


# Security Violation Reporting
# ----------------------------
# The following routes handle the reporting of various types of security violations like CSP, CORS,
# and opener policy violations. These reports are crucial for monitoring potential security threats.

# These routes handle the reporting of various types of security violations like CSP, CORS, and opener policy
# violations. They receive violation reports sent by the user's browser and write them to corresponding log files.
# This is crucial for monitoring and responding to potential security threats.

# These functions are designed to handle reports of various web security violations:
# - csp_violation_report: Handles reports related to Content Security Policy (CSP) violations.
# - embedder_violation_report: Manages reports of violations related to embedding (CORS issues).
# - opener_violation_report: Deals with reports of opener policy violations.

# In each function, if there is data in the request, it is assumed to be a violation report.
# The report data is then written to a corresponding log file (e.g., 'csp-violations.txt').
# This logging is crucial for monitoring and addressing potential security threats on the website.
# The functions return a 204 No Content response if data is received and logged, or a 400 Bad Request response
# if no data is received, indicating an issue with the reporting mechanism.

@unauth.route('/csp-violations', methods=['POST'])
def csp_violation_report():
    """
    This route is dedicated to handling Content Security Policy (CSP) violation reports. CSP is a critical
    security standard used to prevent various types of attacks, including Cross-Site Scripting (XSS) and
    data injection attacks. When a CSP rule is violated, the user's browser sends a report to this route.

    Functionality:
    - Listens for POST requests containing CSP violation reports.
    - Upon receiving a report, the route decodes the data from the request and appends it to a log file
      ('csp-violations.txt'). This log is crucial for web administrators to analyze and address the
      underlying causes of CSP violations.

    Responses:
    - Returns a 204 No Content response when a report is successfully received and logged. This status
      code indicates that the request was successful, but there is no content to send in the response.
    - Returns a 400 Bad Request response if no data is received in the request. This could indicate an
      issue with the client-side reporting mechanism or an empty report being sent.

    Importance:
    - This route is essential for maintaining the security posture of the website. By logging and analyzing
      CSP violations, developers and security personnel can identify and mitigate potential security risks.
    """
    if request.data:
        report = request.data
        with open('csp-violations.txt', 'a') as f:
            f.write(report.decode('utf-8') + '\n')
        return '', 204
    else:
        return 'No data received.', 400


@unauth.route('/embedder-violations', methods=['POST'])
def embedder_violation_report():
    """
    This route manages the reporting of embedder policy violations. An embedder policy is a security
    measure that governs the embedding of external resources and frames in a webpage. Violations of this
    policy are serious as they can lead to security vulnerabilities like Clickjacking or unwanted content
    injection.

    Functionality:
    - Receives POST requests from the user's browser with details about embedder policy violations.
    - The violation report, typically in JSON format, is decoded and appended to a log file
      ('embedder-violations.txt'). This logging is vital for tracking and addressing potential security
      breaches related to embedding third-party content.

    Responses:
    - A 204 No Content response is sent back if the report is successfully logged. This informs the sender
      (usually the browser) that the report was processed successfully.
    - If no data is present in the request, a 400 Bad Request response is returned, indicating a potential
      error in the reporting process or an incorrectly configured policy.

    Importance:
    - Monitoring embedder policy violations helps maintain the integrity of the website's content and
      protect against various web-based attacks. Regular analysis of these reports can aid in strengthening
      the site's security measures.
    """
    if request.data:
        report = request.data
        with open('embedder-violations.txt', 'a') as f:
            f.write(report.decode('utf-8') + '\n')
        return '', 204
    else:
        return 'No data received.', 400


@unauth.route('/opener-violations', methods=['POST'])
def opener_violation_report():
    """
    This route handles the reporting of opener policy violations. These violations are significant
    from a security standpoint as they may indicate unauthorized cross-origin interactions or other
    policy breaches. This reporting mechanism is essential for detecting and addressing potential
    security threats.

    Functionality:
    - Listens for POST requests containing opener policy violation reports.
    - Writes the received reports to a log file ('opener-violations.txt') for further analysis and action.

    Returns:
        - A 204 No Content response for successfully logged reports.
        - A 400 Bad Request response if no report data is received, indicating an issue in the reporting process.
    """
    if request.data:
        report = request.data
        with open('opener-violations.txt', 'a') as f:
            f.write(report.decode('utf-8') + '\n')
        return '', 204
    else:
        return 'No data received.', 400
