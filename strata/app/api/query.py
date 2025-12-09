import logging
from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy import func, select

from app.auth import TenantContext, get_tenant_context
from app.config import settings
from app.models import (
    Agent,
    Chunk,
    Document,
    DocumentExposure,
    File,
    Interaction,
    SensitivityFinding,
    Share,
)
from app.schemas import (
    AccessSummary,
    AgentSearchChunksRequest,
    AgentSearchChunksResponse,
    AgentStatsResponse,
    AnswerWithEvidenceRequest,
    AnswerWithEvidenceResponse,
    ChunkSearchResult,
    DashboardMetrics,
    DocumentDetailResponse,
    EvidenceChunk,
    FieldChangeDetail,
    FindSensitiveContentRequest,
    FindSensitiveContentResponse,
    InteractionListItem,
    InteractionListResponse,
    InteractionTraceResponse,
    RetrievedChunkDetail,
    SearchChunksRequest,
    SearchChunksResponse,
    SemanticDiffRequest,
    SemanticDiffResponse,
    SensitiveContentItem,
    SensitivityFindingDetail,
)
from app.services.observability import (
    InteractionTracker,
    get_agent_interaction_stats,
    get_interaction_trace,
    list_interactions,
)
from app.services.policy_engine import evaluate_chunk_access, get_chunk_text_for_view

logger = logging.getLogger(__name__)
router = APIRouter()


@router.post("/sensitivity/find", response_model=FindSensitiveContentResponse)
async def find_sensitive_content(
    request: FindSensitiveContentRequest,
    ctx: TenantContext = Depends(get_tenant_context),
) -> FindSensitiveContentResponse:
    """
    Find documents with sensitive content, filtered by scope, sensitivity types,
    and exposure levels.
    """
    # Base query for documents with exposure
    query = (
        select(Document, DocumentExposure, File, Share)
        .join(DocumentExposure, DocumentExposure.document_id == Document.id)
        .join(File, File.id == Document.file_id)
        .join(Share, Share.id == File.share_id)
        .where(Document.tenant_id == ctx.tenant_id)
    )

    # Apply scope filters
    if request.scope:
        if request.scope.share_id:
            query = query.where(File.share_id == request.scope.share_id)
        if request.scope.path_prefix:
            query = query.where(File.relative_path.startswith(request.scope.path_prefix))

    # Apply exposure level filter
    if request.exposure_levels:
        query = query.where(DocumentExposure.exposure_level.in_(request.exposure_levels))

    # Apply sensitivity type filter - requires subquery
    if request.sensitivity_types:
        subq = (
            select(SensitivityFinding.document_id)
            .where(
                SensitivityFinding.tenant_id == ctx.tenant_id,
                SensitivityFinding.sensitivity_type.in_(request.sensitivity_types),
            )
            .distinct()
        )
        query = query.where(Document.id.in_(subq))

    # Get total count
    count_query = select(func.count()).select_from(query.subquery())
    total_result = await ctx.session.execute(count_query)
    total = total_result.scalar() or 0

    # Apply pagination
    offset = (request.page - 1) * request.page_size
    query = query.offset(offset).limit(request.page_size)
    query = query.order_by(DocumentExposure.exposure_score.desc())

    # Execute query
    result = await ctx.session.execute(query)
    rows = result.fetchall()

    # Build response items
    items = []
    for doc, exposure, file, share in rows:
        # Get sensitivity summary for this document
        sens_result = await ctx.session.execute(
            select(
                SensitivityFinding.sensitivity_type,
                func.count(SensitivityFinding.id),
            )
            .where(SensitivityFinding.document_id == doc.id)
            .group_by(SensitivityFinding.sensitivity_type)
        )
        sens_counts = {row[0].value: row[1] for row in sens_result.fetchall()}

        items.append(
            SensitiveContentItem(
                document_id=doc.id,
                file_id=file.id,
                share_id=share.id,
                relative_path=file.relative_path,
                file_type=file.file_type,
                sensitivity_summary=sens_counts,
                exposure_level=exposure.exposure_level,
                exposure_score=exposure.exposure_score,
                access_summary=AccessSummary(**exposure.access_summary),
            )
        )

    return FindSensitiveContentResponse(
        items=items,
        page=request.page,
        page_size=request.page_size,
        total=total,
    )


@router.post("/search/chunks", response_model=SearchChunksResponse)
async def search_chunks(
    request: SearchChunksRequest,
    ctx: TenantContext = Depends(get_tenant_context),
) -> SearchChunksResponse:
    """
    Search for chunks matching a query.
    For v0, this is simple text search. Embeddings-based search can be added later.
    """
    # Build search query
    search_term = f"%{request.query}%"

    query = (
        select(Chunk, Document, File)
        .join(Document, Document.id == Chunk.document_id)
        .join(File, File.id == Document.file_id)
        .where(
            Chunk.tenant_id == ctx.tenant_id,
            Chunk.text.ilike(search_term),
        )
    )

    # Apply scope filters
    if request.scope:
        if request.scope.share_id:
            query = query.where(File.share_id == request.scope.share_id)
        if request.scope.path_prefix:
            query = query.where(File.relative_path.startswith(request.scope.path_prefix))

    # Limit results
    query = query.limit(request.k)

    # Execute query
    result = await ctx.session.execute(query)
    rows = result.fetchall()

    # Build response
    results = []
    for chunk, doc, file in rows:
        # Create a snippet from the chunk text
        snippet = chunk.text[:200] + "..." if len(chunk.text) > 200 else chunk.text

        results.append(
            ChunkSearchResult(
                chunk_id=chunk.id,
                document_id=doc.id,
                file_id=file.id,
                relative_path=file.relative_path,
                snippet=snippet,
                score=1.0,  # No real scoring for text search in v0
            )
        )

    return SearchChunksResponse(results=results)


@router.get("/dashboard/metrics", response_model=DashboardMetrics)
async def get_dashboard_metrics(
    ctx: TenantContext = Depends(get_tenant_context),
) -> DashboardMetrics:
    """Get dashboard metrics for the authenticated tenant."""
    # Total files
    result = await ctx.session.execute(
        select(func.count(File.id)).where(
            File.tenant_id == ctx.tenant_id,
            File.deleted == False,  # noqa: E712
        )
    )
    total_files = result.scalar() or 0

    # Total documents
    result = await ctx.session.execute(
        select(func.count(Document.id)).where(Document.tenant_id == ctx.tenant_id)
    )
    total_documents = result.scalar() or 0

    # Documents with findings
    result = await ctx.session.execute(
        select(func.count(func.distinct(SensitivityFinding.document_id))).where(
            SensitivityFinding.tenant_id == ctx.tenant_id
        )
    )
    documents_with_findings = result.scalar() or 0

    # High exposure documents
    result = await ctx.session.execute(
        select(func.count(DocumentExposure.id)).where(
            DocumentExposure.tenant_id == ctx.tenant_id,
            DocumentExposure.exposure_level == "HIGH",
        )
    )
    high_exposure_documents = result.scalar() or 0

    # Findings by type
    result = await ctx.session.execute(
        select(
            SensitivityFinding.sensitivity_type,
            func.count(SensitivityFinding.id),
        )
        .where(SensitivityFinding.tenant_id == ctx.tenant_id)
        .group_by(SensitivityFinding.sensitivity_type)
    )
    findings_by_type = {row[0].value: row[1] for row in result.fetchall()}

    # Documents by exposure level
    result = await ctx.session.execute(
        select(
            DocumentExposure.exposure_level,
            func.count(DocumentExposure.id),
        )
        .where(DocumentExposure.tenant_id == ctx.tenant_id)
        .group_by(DocumentExposure.exposure_level)
    )
    documents_by_exposure = {row[0].value: row[1] for row in result.fetchall()}

    return DashboardMetrics(
        total_files=total_files,
        total_documents=total_documents,
        documents_with_findings=documents_with_findings,
        high_exposure_documents=high_exposure_documents,
        findings_by_type=findings_by_type,
        documents_by_exposure=documents_by_exposure,
    )


@router.get("/documents/{document_id}", response_model=DocumentDetailResponse)
async def get_document_detail(
    document_id: UUID,
    ctx: TenantContext = Depends(get_tenant_context),
) -> DocumentDetailResponse:
    """Get detailed information about a document."""
    # Load document with related data
    result = await ctx.session.execute(
        select(Document, File, Share)
        .join(File, File.id == Document.file_id)
        .join(Share, Share.id == File.share_id)
        .where(
            Document.id == document_id,
            Document.tenant_id == ctx.tenant_id,
        )
    )
    row = result.fetchone()

    if not row:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Document not found",
        )

    doc, file, share = row

    # Get exposure
    result = await ctx.session.execute(
        select(DocumentExposure).where(DocumentExposure.document_id == document_id)
    )
    exposure = result.scalar_one_or_none()

    # Get findings
    result = await ctx.session.execute(
        select(SensitivityFinding)
        .where(SensitivityFinding.document_id == document_id)
        .order_by(SensitivityFinding.created_at)
    )
    findings = result.scalars().all()

    return DocumentDetailResponse(
        id=doc.id,
        file_id=file.id,
        share_id=share.id,
        relative_path=file.relative_path,
        title=doc.title,
        file_type=doc.file_type,
        size_bytes=doc.size_bytes,
        last_indexed_at=doc.last_indexed_at,
        exposure_level=exposure.exposure_level if exposure else None,
        exposure_score=exposure.exposure_score if exposure else None,
        access_summary=AccessSummary(**exposure.access_summary) if exposure else None,
        findings=[
            SensitivityFindingDetail(
                id=f.id,
                sensitivity_type=f.sensitivity_type,
                sensitivity_level=f.sensitivity_level,
                snippet=f.snippet,
                created_at=f.created_at,
            )
            for f in findings
        ],
    )


# ============================================================================
# v0.1: Agent-aware Search with Policy Enforcement and Observability
# ============================================================================


@router.post("/v0/search/chunks", response_model=AgentSearchChunksResponse)
async def search_chunks_v0(
    request: AgentSearchChunksRequest,
    ctx: TenantContext = Depends(get_tenant_context),
) -> AgentSearchChunksResponse:
    """
    Search for chunks with optional agent identity for policy enforcement.

    If agent_id is provided, policies are evaluated for each chunk and
    filtered/redacted content may be returned based on the agent's policies.

    Returns an interaction_id for observability trace lookup.
    """
    search_term = f"%{request.query}%"

    query = (
        select(Chunk, Document, File)
        .join(Document, Document.id == Chunk.document_id)
        .join(File, File.id == Document.file_id)
        .where(
            Chunk.tenant_id == ctx.tenant_id,
            Chunk.text.ilike(search_term),
        )
    )

    # Apply scope filters
    if request.scope:
        if request.scope.share_id:
            query = query.where(File.share_id == request.scope.share_id)
        if request.scope.path_prefix:
            query = query.where(File.relative_path.startswith(request.scope.path_prefix))

    # Get more results than needed for filtering
    query = query.limit(request.k * 2)

    result = await ctx.session.execute(query)
    rows = result.fetchall()

    # Convert scope to dict for observability
    scope_dict = None
    if request.scope:
        scope_dict = {
            "share_id": str(request.scope.share_id) if request.scope.share_id else None,
            "path_prefix": request.scope.path_prefix,
        }

    # Track the interaction
    async with InteractionTracker(
        ctx.session,
        ctx.tenant_id,
        "search_chunks",
        request.query,
        scope=scope_dict,
        agent_id=request.agent_id,
        user_id=request.user_id,
    ) as tracker:
        results = []
        for rank, (chunk, doc, file) in enumerate(rows):
            if len(results) >= request.k:
                break

            # Evaluate policy if agent_id provided
            view_type = "raw"

            if request.agent_id:
                decision = await evaluate_chunk_access(
                    ctx.session,
                    chunk,
                    doc,
                    file.relative_path,
                    request.agent_id,
                    ctx.tenant_id,
                )

                if not decision.allowed:
                    # Record filtered chunk in trace
                    tracker.add_chunk(
                        chunk.id,
                        rank=rank,
                        score=1.0,
                        view_type="filtered",
                        was_filtered=True,
                        filter_reason=decision.filter_reason,
                    )
                    continue

                view_type = decision.view_type

            # Get appropriate text based on view type
            text = get_chunk_text_for_view(chunk, view_type)
            snippet = text[:200] + "..." if len(text) > 200 else text

            # Record in trace
            tracker.add_chunk(
                chunk.id,
                rank=rank,
                score=1.0,
                view_type=view_type,
                was_filtered=False,
            )

            results.append(
                ChunkSearchResult(
                    chunk_id=chunk.id,
                    document_id=doc.id,
                    file_id=file.id,
                    relative_path=file.relative_path,
                    snippet=snippet,
                    score=1.0,
                )
            )

        return AgentSearchChunksResponse(
            results=results,
            interaction_id=tracker.interaction_id,
        )


# ============================================================================
# v0.1: Observability Endpoints
# ============================================================================


@router.get("/v0/interactions/{interaction_id}", response_model=InteractionTraceResponse)
async def get_interaction(
    interaction_id: UUID,
    ctx: TenantContext = Depends(get_tenant_context),
) -> InteractionTraceResponse:
    """Get detailed trace for an interaction."""
    trace = await get_interaction_trace(ctx.session, ctx.tenant_id, interaction_id)

    if not trace:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Interaction not found",
        )

    return InteractionTraceResponse(
        interaction_id=trace.interaction_id,
        interaction_type=trace.interaction_type,
        query=trace.query,
        scope=trace.scope,
        chunks_retrieved=[
            RetrievedChunkDetail(
                chunk_id=c.chunk_id,
                rank=c.rank,
                score=c.score,
                view_type=c.view_type,
                was_filtered=c.was_filtered,
                filter_reason=c.filter_reason,
            )
            for c in trace.chunks_retrieved
        ],
        answer=trace.answer,
        evidence_coverage=trace.evidence_coverage,
        latency_ms=trace.latency_ms,
        agent_id=trace.agent_id,
        user_id=trace.user_id,
    )


@router.get("/v0/interactions", response_model=InteractionListResponse)
async def list_interactions_endpoint(
    agent_id: UUID | None = None,
    interaction_type: str | None = None,
    limit: int = 100,
    offset: int = 0,
    ctx: TenantContext = Depends(get_tenant_context),
) -> InteractionListResponse:
    """List interactions with optional filtering."""
    interactions = await list_interactions(
        ctx.session,
        ctx.tenant_id,
        agent_id=agent_id,
        interaction_type=interaction_type,
        limit=limit,
        offset=offset,
    )

    # Get total count
    count_query = select(func.count(Interaction.id)).where(Interaction.tenant_id == ctx.tenant_id)
    if agent_id:
        count_query = count_query.where(Interaction.agent_id == agent_id)
    if interaction_type:
        count_query = count_query.where(Interaction.interaction_type == interaction_type)

    result = await ctx.session.execute(count_query)
    total = result.scalar() or 0

    items = []
    for i in interactions:
        chunk_count = len(i.chunks) if hasattr(i, "chunks") else 0

        items.append(
            InteractionListItem(
                interaction_id=i.id,
                interaction_type=i.interaction_type,
                query=i.query,
                chunk_count=chunk_count,
                latency_ms=i.latency_ms,
                created_at=i.created_at,
            )
        )

    return InteractionListResponse(items=items, total=total)


@router.get("/v0/agents/{agent_id}/stats", response_model=AgentStatsResponse)
async def get_agent_stats(
    agent_id: UUID,
    ctx: TenantContext = Depends(get_tenant_context),
) -> AgentStatsResponse:
    """Get interaction statistics for an agent."""
    # Verify agent exists and belongs to tenant
    result = await ctx.session.execute(
        select(Agent).where(
            Agent.id == agent_id,
            Agent.tenant_id == ctx.tenant_id,
        )
    )
    agent = result.scalar_one_or_none()

    if not agent:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Agent not found",
        )

    stats = await get_agent_interaction_stats(ctx.session, ctx.tenant_id, agent_id)

    return AgentStatsResponse(**stats)


# ============================================================================
# v0.1: Answer with Evidence
# ============================================================================


@router.post("/v0/answer_with_evidence", response_model=AnswerWithEvidenceResponse)
async def answer_with_evidence(
    request: AnswerWithEvidenceRequest,
    ctx: TenantContext = Depends(get_tenant_context),
) -> AnswerWithEvidenceResponse:
    """
    Answer a question with evidence from the document corpus.

    Retrieves relevant chunks, applies policy filtering if agent_id provided,
    generates an answer using LLM, and returns the answer with source evidence.
    """
    if not settings.openai_api_key:
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail="Answer generation requires OpenAI API key",
        )

    # Search for relevant chunks
    search_term = f"%{request.question}%"

    query = (
        select(Chunk, Document, File)
        .join(Document, Document.id == Chunk.document_id)
        .join(File, File.id == Document.file_id)
        .where(
            Chunk.tenant_id == ctx.tenant_id,
            Chunk.text.ilike(search_term),
        )
    )

    # Apply scope filters
    if request.scope:
        if request.scope.share_id:
            query = query.where(File.share_id == request.scope.share_id)
        if request.scope.path_prefix:
            query = query.where(File.relative_path.startswith(request.scope.path_prefix))

    # Get more results for filtering
    query = query.limit(request.k * 2)

    result = await ctx.session.execute(query)
    rows = result.fetchall()

    # Convert scope to dict for observability
    scope_dict = None
    if request.scope:
        scope_dict = {
            "share_id": str(request.scope.share_id) if request.scope.share_id else None,
            "path_prefix": request.scope.path_prefix,
        }

    # Track the interaction
    async with InteractionTracker(
        ctx.session,
        ctx.tenant_id,
        "answer_with_evidence",
        request.question,
        scope=scope_dict,
        agent_id=request.agent_id,
        user_id=request.user_id,
    ) as tracker:
        evidence = []
        context_texts = []

        for rank, (chunk, doc, file) in enumerate(rows):
            if len(evidence) >= request.k:
                break

            # Evaluate policy if agent_id provided
            view_type = "raw"

            if request.agent_id:
                decision = await evaluate_chunk_access(
                    ctx.session,
                    chunk,
                    doc,
                    file.relative_path,
                    request.agent_id,
                    ctx.tenant_id,
                )

                if not decision.allowed:
                    tracker.add_chunk(
                        chunk.id,
                        rank=rank,
                        score=1.0,
                        view_type="filtered",
                        was_filtered=True,
                        filter_reason=decision.filter_reason,
                    )
                    continue

                view_type = decision.view_type

            # Get appropriate text
            text = get_chunk_text_for_view(chunk, view_type)

            tracker.add_chunk(
                chunk.id,
                rank=rank,
                score=1.0,
                view_type=view_type,
                was_filtered=False,
            )

            evidence.append(
                EvidenceChunk(
                    chunk_id=chunk.id,
                    document_id=doc.id,
                    file_id=file.id,
                    relative_path=file.relative_path,
                    section_path=chunk.section_path,
                    text=text,
                    score=1.0,
                )
            )
            context_texts.append(f"[{file.relative_path}]\n{text}")

        if not evidence:
            # No relevant evidence found
            tracker.set_answer(
                "I could not find relevant information to answer this question.", 0.0
            )
            return AnswerWithEvidenceResponse(
                answer="I could not find relevant information to answer this question.",
                evidence=[],
                evidence_coverage=0.0,
                interaction_id=tracker.interaction_id,
            )

        # Generate answer using LLM
        try:
            from openai import AsyncOpenAI

            client = AsyncOpenAI(api_key=settings.openai_api_key)

            context = "\n\n---\n\n".join(context_texts)

            prompt = (
                "You are a helpful assistant answering questions based on "
                "provided document evidence.\n\n"
                f"Question: {request.question}\n\n"
                f"Relevant document excerpts:\n{context}\n\n"
                "Based ONLY on the evidence provided above, answer the question. "
                "If the evidence doesn't contain enough information to fully answer "
                "the question, say so. Be specific and cite which documents support "
                "your answer.\n\n"
                "Answer:"
            )

            response = await client.chat.completions.create(
                model="gpt-4o-mini",
                messages=[{"role": "user", "content": prompt}],
                max_tokens=500,
                temperature=0.3,
            )

            answer = response.choices[0].message.content.strip()

            # Simple evidence coverage heuristic based on chunks used
            evidence_coverage = min(1.0, len(evidence) / request.k)

            tracker.set_answer(answer, evidence_coverage)

            return AnswerWithEvidenceResponse(
                answer=answer,
                evidence=evidence,
                evidence_coverage=evidence_coverage,
                interaction_id=tracker.interaction_id,
            )

        except Exception as e:
            logger.exception(f"Failed to generate answer: {e}")
            raise HTTPException(
                status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
                detail="Failed to generate answer",
            ) from e


# ============================================================================
# v0.1: Semantic Diff
# ============================================================================


@router.post("/v0/semantic_diff", response_model=SemanticDiffResponse)
async def compute_semantic_diff(
    request: SemanticDiffRequest,
    ctx: TenantContext = Depends(get_tenant_context),
) -> SemanticDiffResponse:
    """
    Compute semantic diff between two document versions.

    Returns structured field changes and a natural language summary.
    """
    from app.services.semantic_diff import get_or_compute_diff

    diff = await get_or_compute_diff(
        ctx.session,
        ctx.tenant_id,
        request.from_version_id,
        request.to_version_id,
    )

    if not diff:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="One or both document versions not found",
        )

    return SemanticDiffResponse(
        from_version_id=diff.from_version_id,
        to_version_id=diff.to_version_id,
        field_changes=[
            FieldChangeDetail(
                field_name=fc.field_name,
                old_value=str(fc.old_value) if fc.old_value is not None else None,
                new_value=str(fc.new_value) if fc.new_value is not None else None,
                change_type=fc.change_type,
            )
            for fc in diff.field_changes
        ],
        summary=diff.summary,
    )
