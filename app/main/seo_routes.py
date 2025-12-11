# app/main/seo_routes.py
# SEO-related routes: sitemap.xml, robots.txt

from flask import Response, url_for, request
from app.main import bp
from app.extensions import db
from app.models import User, Country, Region
from datetime import datetime


@bp.route('/sitemap.xml')
def sitemap():
    """Generate dynamic sitemap.xml for search engines."""
    base_url = request.url_root.rstrip('/')

    # Start XML
    xml = ['<?xml version="1.0" encoding="UTF-8"?>']
    xml.append('<urlset xmlns="http://www.sitemaps.org/schemas/sitemap/0.9">')

    # Static pages with priorities
    static_pages = [
        ('main.index', '1.0', 'daily'),
        ('main.game_guide', '0.8', 'weekly'),
        ('main.about', '0.5', 'monthly'),
        ('main.faq', '0.6', 'weekly'),
        ('main.terms_of_service', '0.3', 'monthly'),
        ('main.privacy_policy', '0.3', 'monthly'),
    ]

    for endpoint, priority, changefreq in static_pages:
        try:
            url = url_for(endpoint, _external=True)
            xml.append(f'''  <url>
    <loc>{url}</loc>
    <changefreq>{changefreq}</changefreq>
    <priority>{priority}</priority>
  </url>''')
        except Exception:
            pass

    # Public user profiles (users with usernames)
    users = db.session.scalars(
        db.select(User)
        .filter(User.username.isnot(None))
        .filter(User.is_deleted == False)
        .filter(User.is_banned == False)
        .order_by(User.experience.desc())
        .limit(1000)  # Top 1000 players
    ).all()

    for user in users:
        try:
            url = url_for('main.view_profile', username=user.username, _external=True)
            xml.append(f'''  <url>
    <loc>{url}</loc>
    <changefreq>weekly</changefreq>
    <priority>0.6</priority>
  </url>''')
        except Exception:
            pass

    # Countries
    countries = db.session.scalars(
        db.select(Country)
        .filter(Country.is_deleted == False)
        .order_by(Country.name)
    ).all()

    for country in countries:
        try:
            url = url_for('main.country', slug=country.slug, _external=True)
            xml.append(f'''  <url>
    <loc>{url}</loc>
    <changefreq>daily</changefreq>
    <priority>0.7</priority>
  </url>''')
        except Exception:
            pass

    # Regions
    regions = db.session.scalars(
        db.select(Region)
        .filter(Region.is_deleted == False)
        .order_by(Region.name)
    ).all()

    for region in regions:
        try:
            url = url_for('main.region', slug=region.slug, _external=True)
            xml.append(f'''  <url>
    <loc>{url}</loc>
    <changefreq>daily</changefreq>
    <priority>0.5</priority>
  </url>''')
        except Exception:
            pass

    xml.append('</urlset>')

    return Response('\n'.join(xml), mimetype='application/xml')
