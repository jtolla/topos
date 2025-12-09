import logging
import os
from datetime import datetime
from uuid import uuid4

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy import delete, select

from app.auth import TenantContext, get_tenant_context
from app.models import (
    File,
    FileAclEntry,
    FileEffectiveAccess,
    FileEvent,
    FileEventType,
    Job,
    JobType,
    Principal,
    PrincipalType,
    Share,
)
from app.schemas import (
    AclEntryInput,
    FileEventInput,
    IngestEventsRequest,
    IngestEventsResponse,
)

logger = logging.getLogger(__name__)
router = APIRouter()


async def get_or_create_share(
    ctx: TenantContext,
    share_name: str,
) -> Share:
    """Get share by name, or raise 400 if not found."""
    result = await ctx.session.execute(
        select(Share).where(
            Share.tenant_id == ctx.tenant_id,
            Share.name == share_name,
        )
    )
    share = result.scalar_one_or_none()
    if not share:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"Share '{share_name}' not found. Create it first via /v0/admin/share",
        )
    return share


async def get_or_create_principal(
    ctx: TenantContext,
    external_id: str,
    display_name: str | None,
    principal_type: str,
) -> Principal:
    """Get or create a principal by external ID."""
    result = await ctx.session.execute(
        select(Principal).where(
            Principal.tenant_id == ctx.tenant_id,
            Principal.external_id == external_id,
        )
    )
    principal = result.scalar_one_or_none()

    if not principal:
        ptype = (
            PrincipalType(principal_type)
            if principal_type in [t.value for t in PrincipalType]
            else PrincipalType.USER
        )
        principal = Principal(
            id=uuid4(),
            tenant_id=ctx.tenant_id,
            type=ptype,
            external_id=external_id,
            display_name=display_name or external_id,
        )
        ctx.session.add(principal)
        await ctx.session.flush()

    return principal


async def process_acl_entries(
    ctx: TenantContext,
    file: File,
    acl_entries: list[AclEntryInput],
) -> None:
    """Process ACL entries for a file - delete old ones and insert new."""
    # Delete existing ACL entries for this file
    await ctx.session.execute(delete(FileAclEntry).where(FileAclEntry.file_id == file.id))
    await ctx.session.execute(
        delete(FileEffectiveAccess).where(FileEffectiveAccess.file_id == file.id)
    )

    # Create new ACL entries
    for entry in acl_entries:
        principal = await get_or_create_principal(
            ctx,
            entry.principal_external_id,
            entry.principal_display_name,
            entry.principal_type,
        )

        # Create ACL entry
        acl_entry = FileAclEntry(
            id=uuid4(),
            tenant_id=ctx.tenant_id,
            file_id=file.id,
            principal_id=principal.id,
            rights=entry.rights,
            source=entry.source,
        )
        ctx.session.add(acl_entry)

        # Create effective access (for v0, anyone with any rights can read)
        effective = FileEffectiveAccess(
            id=uuid4(),
            tenant_id=ctx.tenant_id,
            file_id=file.id,
            principal_id=principal.id,
            can_read=True,
        )
        ctx.session.add(effective)


async def process_file_event(
    ctx: TenantContext,
    event: FileEventInput,
) -> int:
    """
    Process a single file event and return number of jobs created.
    """
    jobs_created = 0
    share = await get_or_create_share(ctx, event.share_name)
    now = datetime.utcnow()

    # Look for existing file
    result = await ctx.session.execute(
        select(File).where(
            File.tenant_id == ctx.tenant_id,
            File.share_id == share.id,
            File.relative_path == event.relative_path,
        )
    )
    existing_file = result.scalar_one_or_none()

    if event.type == FileEventType.FILE_DELETED:
        if existing_file:
            existing_file.deleted = True
            existing_file.last_seen_at = now
            # Record event
            file_event = FileEvent(
                id=uuid4(),
                tenant_id=ctx.tenant_id,
                file_id=existing_file.id,
                share_id=share.id,
                event_type=event.type,
                payload={"relative_path": event.relative_path},
            )
            ctx.session.add(file_event)
        return 0

    # FILE_DISCOVERED or FILE_MODIFIED
    if not existing_file:
        # New file
        file = File(
            id=uuid4(),
            tenant_id=ctx.tenant_id,
            share_id=share.id,
            relative_path=event.relative_path,
            name=os.path.basename(event.relative_path),
            size_bytes=event.size_bytes or 0,
            mtime=event.mtime or now,
            file_type=event.file_type or "application/octet-stream",
            content_hash=event.content_hash or "",
            acl_hash=event.acl_hash or "",
            last_seen_at=now,
            deleted=False,
        )
        ctx.session.add(file)
        await ctx.session.flush()

        # Process ACLs
        if event.acl_entries:
            await process_acl_entries(ctx, file, event.acl_entries)

        # Record event
        file_event = FileEvent(
            id=uuid4(),
            tenant_id=ctx.tenant_id,
            file_id=file.id,
            share_id=share.id,
            event_type=event.type,
            payload={
                "relative_path": event.relative_path,
                "size_bytes": event.size_bytes,
                "file_type": event.file_type,
            },
        )
        ctx.session.add(file_event)

        # Create extraction job
        job = Job(
            id=uuid4(),
            tenant_id=ctx.tenant_id,
            job_type=JobType.EXTRACT_CONTENT,
            file_id=file.id,
        )
        ctx.session.add(job)
        jobs_created = 1

    else:
        # Existing file - check for changes
        content_changed = event.content_hash and event.content_hash != existing_file.content_hash
        acl_changed = event.acl_hash and event.acl_hash != existing_file.acl_hash

        if not content_changed and not acl_changed:
            # No changes, just update last_seen
            existing_file.last_seen_at = now
            existing_file.deleted = False
            return 0

        # Update file metadata
        if event.size_bytes is not None:
            existing_file.size_bytes = event.size_bytes
        if event.mtime is not None:
            existing_file.mtime = event.mtime
        if event.file_type is not None:
            existing_file.file_type = event.file_type
        if event.content_hash is not None:
            existing_file.content_hash = event.content_hash
        if event.acl_hash is not None:
            existing_file.acl_hash = event.acl_hash
        existing_file.last_seen_at = now
        existing_file.deleted = False

        # Determine event type
        if content_changed:
            recorded_type = FileEventType.FILE_MODIFIED
        else:
            recorded_type = FileEventType.ACL_CHANGED

        # Process ACLs if changed
        if acl_changed and event.acl_entries:
            await process_acl_entries(ctx, existing_file, event.acl_entries)

        # Record event
        file_event = FileEvent(
            id=uuid4(),
            tenant_id=ctx.tenant_id,
            file_id=existing_file.id,
            share_id=share.id,
            event_type=recorded_type,
            payload={
                "relative_path": event.relative_path,
                "content_changed": content_changed,
                "acl_changed": acl_changed,
            },
        )
        ctx.session.add(file_event)

        # Create extraction job only if content changed
        if content_changed:
            job = Job(
                id=uuid4(),
                tenant_id=ctx.tenant_id,
                job_type=JobType.EXTRACT_CONTENT,
                file_id=existing_file.id,
            )
            ctx.session.add(job)
            jobs_created = 1

    return jobs_created


@router.post("/events", response_model=IngestEventsResponse)
async def ingest_events(
    request: IngestEventsRequest,
    ctx: TenantContext = Depends(get_tenant_context),
) -> IngestEventsResponse:
    """
    Ingest file events from an agent.
    Creates/updates files and schedules extraction jobs as needed.
    """
    total_jobs = 0

    for event in request.events:
        try:
            jobs = await process_file_event(ctx, event)
            total_jobs += jobs
        except Exception as e:
            logger.exception(f"Error processing event for {event.relative_path}: {e}")
            # Continue processing other events

    await ctx.session.commit()

    logger.info(
        f"Processed {len(request.events)} events from agent {request.agent_id}, "
        f"created {total_jobs} jobs"
    )

    return IngestEventsResponse(
        processed=len(request.events),
        jobs_created=total_jobs,
    )
