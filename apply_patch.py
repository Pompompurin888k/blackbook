import re

content = open('web/routes/portal_actions.py').read()

# Replace Imports
content = re.sub(
    r'from fastapi import APIRouter, Form, Request\nfrom fastapi.responses import HTMLResponse, RedirectResponse\nfrom fastapi.templating import Jinja2Templates',
    'from fastapi import APIRouter, Form, Request, UploadFile, File\nfrom fastapi.responses import HTMLResponse, RedirectResponse\nfrom fastapi.templating import Jinja2Templates',
    content
)

content = re.sub(
    r'    VALID_PACKAGE_DAYS,\n\)',
    '    VALID_PACKAGE_DAYS,\n    ONBOARDING_MAX_FILE_SIZE_MB,\n    ONBOARDING_ALLOWED_EXTENSIONS,\n)',
    content
)

content = re.sub(
    r'from utils.db_async import db_call\nfrom utils.providers import _to_string_list\n\nrouter = APIRouter\(\)',
    'from utils.db_async import db_call\nfrom utils.providers import _to_string_list\nfrom utils.uploads import _save_provider_upload\n\nrouter = APIRouter()',
    content
)

# Replace the End of File
additions = '''
@router.post("/provider/story/upload")
async def provider_story_upload(
    request: Request,
    file: UploadFile = File(...)
):
    """Uploads a new 24-hour story photo."""
    provider, redirect = await _get_provider_or_redirect(request)
    if redirect:
        return redirect

    tg_id = int(provider.get("telegram_id") or 0)
    
    # Validate file size
    file.file.seek(0, 2)
    file_size_mb = file.file.tell() / (1024 * 1024)
    file.file.seek(0)
    if file_size_mb > ONBOARDING_MAX_FILE_SIZE_MB:
        return _portal_redirect("/provider/dashboard", error=f"File too large. Max {ONBOARDING_MAX_FILE_SIZE_MB}MB.")

    # Validate file extension
    ext = file.filename.split(".")[-1].lower() if file.filename else ""
    if f".{ext}" not in ONBOARDING_ALLOWED_EXTENSIONS:
        return _portal_redirect("/provider/dashboard", error="Invalid file format.")

    try:
        # Save photo using existing upload utility
        photo_url = await _save_provider_upload(file.file, file.filename)
        if not photo_url:
            return _portal_redirect("/provider/dashboard", error="Could not save story photo. Please try again.")
            
        # Update database with new photo and timestamp
        success = await db_call(db.update_provider_story, tg_id, photo_url)
        if not success:
            return _portal_redirect("/provider/dashboard", error="Failed to save story to database.")
            
        from services.redis_service import _invalidate_provider_listing_cache
        _invalidate_provider_listing_cache()
        return _portal_redirect("/provider/dashboard", notice="Story uploaded successfully! It will disappear in 24 hours.")
        
    except Exception as e:
        import logging
        logger = logging.getLogger(__name__)
        logger.error(f"Error uploading story: {e}")
        return _portal_redirect("/provider/dashboard", error="An error occurred while uploading. Please try again.")

@router.post("/provider/story/delete")
async def provider_story_delete(request: Request):
    """Deletes the current active story."""
    provider, redirect = await _get_provider_or_redirect(request)
    if redirect:
        return redirect

    tg_id = int(provider.get("telegram_id") or 0)
    
    success = await db_call(db.update_provider_story, tg_id, None)
    if not success:
        return _portal_redirect("/provider/dashboard", error="Failed to delete story.")
        
    from services.redis_service import _invalidate_provider_listing_cache
    _invalidate_provider_listing_cache()
    return _portal_redirect("/provider/dashboard", notice="Story deleted successfully.")
'''

content += additions

open('web/routes/portal_actions.py', 'w').write(content)
print('Patched successfully!')
