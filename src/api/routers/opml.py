"""OPML import/export router."""

from typing import Annotated

from fastapi import APIRouter, Depends, File, HTTPException, UploadFile, status
from fastapi.responses import Response
from sqlalchemy.orm import Session

from application.services.opml import OPMLParseError, opml_service
from infrastructure.database import get_session

router = APIRouter(prefix="/api/opml", tags=["opml"])


@router.get("/export")
def export_opml(
    session: Annotated[Session, Depends(get_session)],
) -> Response:
    """Export all feeds as OPML file."""
    xml_content = opml_service.export(session, title="Feedy Feeds")

    return Response(
        content=xml_content,
        media_type="application/xml",
        headers={
            "Content-Disposition": "attachment; filename=feeds.opml",
        },
    )


@router.post("/import")
def import_opml(
    session: Annotated[Session, Depends(get_session)],
    file: Annotated[UploadFile, File(description="OPML file to import")],
) -> dict[str, int | list[str]]:
    """
    Import feeds from an OPML file.

    Returns counts of created categories, created feeds, skipped feeds,
    and any errors encountered.
    """
    # Validate file type
    if file.filename and not file.filename.lower().endswith((".opml", ".xml")):
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="File must be an OPML or XML file",
        )

    try:
        content = file.file.read()
    except Exception:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Failed to read uploaded file",
        )

    if not content:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Uploaded file is empty",
        )

    try:
        result = opml_service.import_feeds(session, content)
    except OPMLParseError as e:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=str(e),
        )

    return {
        "categories_created": result.categories_created,
        "feeds_created": result.feeds_created,
        "feeds_skipped": result.feeds_skipped,
        "errors": result.errors,
    }
