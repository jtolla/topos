import fnmatch
import hashlib
import logging
import mimetypes
import os
from dataclasses import dataclass, field
from datetime import datetime
from pathlib import Path

from strata_agent.config import ShareConfig

logger = logging.getLogger(__name__)

# Initialize mimetypes
mimetypes.init()


@dataclass
class AclEntry:
    """Represents an ACL entry for a file."""

    principal_external_id: str
    principal_display_name: str
    principal_type: str = "USER"
    rights: str = "R"
    source: str = "FILE"


@dataclass
class FileInfo:
    """Information about a scanned file."""

    share_name: str
    relative_path: str
    size_bytes: int
    mtime: datetime
    file_type: str
    content_hash: str
    acl_hash: str
    acl_entries: list[AclEntry] = field(default_factory=list)


def compute_file_hash(path: str, chunk_size: int = 8192) -> str:
    """Compute SHA256 hash of file contents."""
    sha256 = hashlib.sha256()
    try:
        with open(path, "rb") as f:
            while chunk := f.read(chunk_size):
                sha256.update(chunk)
        return f"sha256:{sha256.hexdigest()}"
    except Exception as e:
        logger.warning(f"Could not hash file {path}: {e}")
        return ""


def compute_acl_hash(acl_entries: list[AclEntry]) -> str:
    """Compute hash of ACL entries for change detection."""
    if not acl_entries:
        return "sha256:empty"

    # Sort entries for consistent hashing
    sorted_entries = sorted(
        acl_entries,
        key=lambda e: (e.principal_external_id, e.rights, e.source),
    )

    content = "|".join(f"{e.principal_external_id}:{e.rights}:{e.source}" for e in sorted_entries)
    return f"sha256:{hashlib.sha256(content.encode()).hexdigest()}"


def get_mime_type(path: str) -> str:
    """Get MIME type for a file."""
    mime_type, _ = mimetypes.guess_type(path)
    return mime_type or "application/octet-stream"


def get_acl_entries(path: str) -> list[AclEntry]:
    """
    Get ACL entries for a file.

    For v0, this is a simplified implementation that returns placeholder entries.
    In production, you would use platform-specific ACL APIs or parse getfacl output.
    """
    # Placeholder: return a simple entry based on file owner
    try:
        stat = os.stat(path)
        uid = stat.st_uid

        # Create a placeholder principal based on UID
        return [
            AclEntry(
                principal_external_id=f"uid:{uid}",
                principal_display_name=f"User {uid}",
                principal_type="USER",
                rights="RW",
                source="FILE",
            )
        ]
    except Exception as e:
        logger.warning(f"Could not get ACL for {path}: {e}")
        return []


def should_exclude(path: str, patterns: list[str]) -> bool:
    """Check if a path should be excluded based on patterns."""
    basename = os.path.basename(path)
    for pattern in patterns:
        if fnmatch.fnmatch(basename, pattern):
            return True
        if fnmatch.fnmatch(path, pattern):
            return True
    return False


def scan_share(config: ShareConfig) -> list[FileInfo]:
    """
    Scan a share and return information about all files.

    Args:
        config: Share configuration

    Returns:
        List of FileInfo objects for all discovered files
    """
    files: list[FileInfo] = []
    mount_point = Path(config.mount_point)

    if not mount_point.exists():
        logger.error(f"Mount point does not exist: {mount_point}")
        return files

    logger.info(f"Scanning share {config.name} at {mount_point}")

    for include_path in config.include_paths:
        scan_root = mount_point / include_path.lstrip("/")

        if not scan_root.exists():
            logger.warning(f"Include path does not exist: {scan_root}")
            continue

        for root, dirs, filenames in os.walk(scan_root):
            # Filter out excluded directories
            dirs[:] = [d for d in dirs if not should_exclude(d, config.exclude_patterns)]

            for filename in filenames:
                if should_exclude(filename, config.exclude_patterns):
                    continue

                full_path = os.path.join(root, filename)

                # Skip if too large
                try:
                    stat = os.stat(full_path)
                    if stat.st_size > config.max_file_size_bytes:
                        logger.debug(f"Skipping large file: {full_path}")
                        continue
                except OSError as e:
                    logger.warning(f"Could not stat file {full_path}: {e}")
                    continue

                # Compute relative path from mount point
                relative_path = os.path.relpath(full_path, mount_point)

                # Get file info
                try:
                    acl_entries = get_acl_entries(full_path)

                    file_info = FileInfo(
                        share_name=config.name,
                        relative_path=relative_path,
                        size_bytes=stat.st_size,
                        mtime=datetime.fromtimestamp(stat.st_mtime),
                        file_type=get_mime_type(full_path),
                        content_hash=compute_file_hash(full_path),
                        acl_hash=compute_acl_hash(acl_entries),
                        acl_entries=acl_entries,
                    )
                    files.append(file_info)
                except Exception as e:
                    logger.exception(f"Error processing file {full_path}: {e}")

    logger.info(f"Found {len(files)} files in share {config.name}")
    return files
