from datetime import datetime

def get_company_image(company_type, quality_level):
    """
    Get the image filename for a company based on its type and quality.

    Args:
        company_type: CompanyType enum or string value
        quality_level: Integer 1-5

    Returns:
        String path relative to static folder
    """
    from app.models.company import CompanyType

    # Map company types to image prefixes
    type_to_image = {
        CompanyType.RIFLE_MANUFACTURING: 'Rifle',
        CompanyType.TANK_MANUFACTURING: 'Tank',
        CompanyType.HELICOPTER_MANUFACTURING: 'Heli',
        CompanyType.FARMING: 'Farm',
        CompanyType.RESOURCE_EXTRACTION: 'Extractor',
        CompanyType.MINING: 'Mine',
    }

    # Handle both enum and string inputs
    if isinstance(company_type, str):
        try:
            company_type = CompanyType(company_type)
        except ValueError:
            return 'images/companies/placeholder.png'

    image_name = type_to_image.get(company_type)

    if image_name:
        return f'images/companies/Q{quality_level}{image_name}.png'
    else:
        return 'images/companies/placeholder.png'

def utility_processor():
    return dict(
        current_year=datetime.utcnow().year,
        now_utc=datetime.utcnow(),
        get_company_image=get_company_image
    )

def inject_forms():
    return dict()
