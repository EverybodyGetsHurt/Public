from flask_login import login_required, current_user
from flask import Blueprint, render_template, send_from_directory, jsonify, make_response, request
from flask.globals import request
from datetime import timedelta

unauth = Blueprint('unauth', __name__)


@login_required
@unauth.route('/', methods=['GET', 'POST'])
@unauth.route('/unauthhome', methods=['GET', 'POST'])
def unauthhome():
    """
    The Home page for unauthorized/public accounts.
    :return:
    """
    return render_template(
        "unauthhome.html", user=current_user, title="home", description="Explore Benemortasia.com, a tool to manage "
                                                                        "Twitter Impersonators for our beloved Crypto"
                                                                        " Channels with ease.")


@unauth.route('/unauthabout')
def unauthabout():
    """
    The About page for unauthorized/public accounts.
    :return:
    """
    return render_template(
        "unauthabout.html", user=current_user, title="about", description="Discover the story of Benemortasia.com, "
                                                                          "our mission, the communities and the "
                                                                          "dedicated team behind it all")


@unauth.route('/gdpr-popup', methods=['GET'])
def gdpr_popup():
    """
    The GDPR popup script for unauthorized/public accounts.
    :return:
    """
    # Check if the user has already given consent (cookie is set)
    gdpr_consent = request.cookies.get('ChewbaccaTheCookie')
    if gdpr_consent == 'accepted':
        # If the user has already given consent, no need to show the popup again
        return make_response('Consent already given.', 200)

    # If the user hasn't given consent, serve the GDPR popup template
    response = make_response(render_template('GDPRrrrAAHrRRhHrAaahrrrrr.html'))
    response.headers['Content-Type'] = 'text/html'
    response.headers['Content-Security-Policy'] = f"default-src 'self' 'nonce-{csp_nonce()}'"
    return response


@unauth.route('/privacypolicy')
def privacypolicy():
    """
    Serve the Privacy Policy page.
    :return: Privacy Policy template
    """
    # Check if the user has already given consent (cookie is set)
    gdpr_consent = request.cookies.get('ChewbaccaTheCookie')
    if gdpr_consent != 'accepted':
        # If the user hasn't given consent, set the cookie to "accepted"
        response = make_response(render_template(
            "privacypolicy.html", user=current_user, title="privacy policy", description="Learn how we protect your "
                                                                                         "data at Benemortasia.com by"
                                                                                         " reading our detailed "
                                                                                         "privacy and security "
                                                                                         "policy."))
        response.set_cookie("ChewbaccaTheCookie", value="accepted", secure=True, httponly=True, samesite='Strict')
        return response

    # If the user has already given consent, no need to show the popup again
    return render_template(
        "privacypolicy.html", user=current_user, title="privacy policy", description="Learn how we protect your data "
                                                                                     "at Benemortasia.com by reading "
                                                                                     "our detailed privacy and "
                                                                                     "security policy.")


@unauth.route('/.well-known/security.txt')
def serve_security_txt():
    """
    # WORKS v2 (Tested Online, https://lifelessandcalm.com/.well-known/security.txt)
    :return:
    """
    return send_from_directory('/home/everybodygetshurt/everybodygetshurt/webapp/static/.well-known',
                               'security.txt')


@unauth.route('/.well-known/pgp-key.asc')
def serve_pgp_key_asc():
    """
    # WORKS v2 (Tested Online, https://lifelessandcalm.com.com/.well-known/security.txt)
    :return:
    """
    return send_from_directory('/home/everybodygetshurt/everybodygetshurt/webapp/static/.well-known',
                               'pgp-key.asc')


@unauth.route('/robots.txt')
def serve_robots_txt():
    """
    # WORKS v2 (Tested Online, https://lifelessandcalm.com/robots.txt)
    :return:
    """

    @after_this_request
    def add_header(response):
        response.headers['Content-Type'] = 'text/html'
        response.headers['X-Content-Type-Options'] = 'nosniff'
        return response

    return send_from_directory('/home/everybodygetshurt/everybodygetshurt/webapp/static/.well-known',
                               'robots.txt')


@unauth.route('/sitemap.xml')
def serve_sitemap_xml():
    """
    # WORKS v2 (Tested Online, https://lifelessandcalm.com/sitemap.xml)
    :return:
    """

    @after_this_request
    def add_header(response):
        response.headers['Content-Type'] = 'xml/html'
        response.headers['X-Content-Type-Options'] = 'nosniff'
        return response

    return send_from_directory('/home/everybodygetshurt/everybodygetshurt/webapp/static/.well-known',
                               'sitemap.xml')


@unauth.route('/csp-violations', methods=['POST'])
def csp_violation_report():
    """
    The Reporting uri to write the csp-violations to csp-violations.txt.
    :return:
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
    The Reporting uri to write the cors-violations to embedder-violations.txt.
    :return:
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
    The Reporting uri to write the cors-violations to opener-violations.txt.
    :return:
    """
    if request.data:
        report = request.data
        with open('opener-violations.txt', 'a') as f:
            f.write(report.decode('utf-8') + '\n')
        return '', 204
    else:
        return 'No data received.', 400
