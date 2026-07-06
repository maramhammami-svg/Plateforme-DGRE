import os
from uuid import uuid4
from pathlib import Path

from fastapi import APIRouter, Depends, HTTPException, Request, UploadFile, File, Form, status
from fastapi.responses import FileResponse
from sqlalchemy import or_
from sqlalchemy.orm import Session

from ..config import settings
from ..database import get_db
from ..deps import get_current_user, scoped_unite_ids, ancestor_unite_ids
from ..models import Document, DocumentShare, UniteOrganisationnelle, User
from ..schemas import DocumentOut, SharedTargetOut
from ..events import log_event
from .. import constants as C

router = APIRouter(prefix="/documents", tags=["documents"])


def _unite_nom(entite):
    """Nom de l'unite d'un user ou d'un document, ou None."""
    u = getattr(entite, "unite", None)
    return u.nom if u is not None else None


def _visible_documents_query(db: Session, user: User):
    """Documents visibles par user : proprietaire, role global, meme arborescence
    d'unite que le proprietaire (comportement historique), ou partage explicite
    (vers cet utilisateur, ou vers une unite dont il est membre/descendant)."""
    ids = scoped_unite_ids(db, user)
    q = db.query(Document)
    if ids is None:
        return q
    my_ancestors = ancestor_unite_ids(db, user.unite_id)
    return (q.outerjoin(DocumentShare, DocumentShare.document_id == Document.id)
            .filter(or_(
                Document.owner_id == user.id,
                Document.unite_id.in_(ids),
                DocumentShare.user_id == user.id,
                DocumentShare.unite_id.in_(my_ancestors),
            ))
            .distinct())


def _can_access(db: Session, user: User, doc: Document) -> bool:
    if doc.owner_id == user.id:
        return True
    ids = scoped_unite_ids(db, user)
    if ids is None or doc.unite_id in ids:
        return True
    my_ancestors = ancestor_unite_ids(db, user.unite_id)
    return (db.query(DocumentShare)
            .filter(DocumentShare.document_id == doc.id)
            .filter(or_(DocumentShare.user_id == user.id,
                       DocumentShare.unite_id.in_(my_ancestors)))
            .first() is not None)


def _partages_by_document(db: Session, doc_ids: list[int]) -> dict[int, list[SharedTargetOut]]:
    if not doc_ids:
        return {}
    rows = db.query(DocumentShare).filter(DocumentShare.document_id.in_(doc_ids)).all()
    unite_ids = {r.unite_id for r in rows if r.unite_id is not None}
    user_ids = {r.user_id for r in rows if r.user_id is not None}
    unites = {u.id: u.nom for u in
             db.query(UniteOrganisationnelle).filter(UniteOrganisationnelle.id.in_(unite_ids)).all()} if unite_ids else {}
    users = {u.id: (u.full_name or u.username) for u in
            db.query(User).filter(User.id.in_(user_ids)).all()} if user_ids else {}
    out: dict[int, list[SharedTargetOut]] = {}
    for r in rows:
        if r.unite_id is not None:
            item = SharedTargetOut(type="unite", id=r.unite_id, nom=unites.get(r.unite_id, "?"))
        else:
            item = SharedTargetOut(type="user", id=r.user_id, nom=users.get(r.user_id, "?"))
        out.setdefault(r.document_id, []).append(item)
    return out


def _to_out(doc: Document, partages: list[SharedTargetOut]) -> DocumentOut:
    return DocumentOut(
        id=doc.id, nom=doc.nom, mime_type=doc.mime_type, owner_id=doc.owner_id,
        unite_id=doc.unite_id, taille_ko=doc.taille_ko, created_at=doc.created_at,
        partages=partages,
    )


@router.post("", response_model=DocumentOut)
async def upload_document(request: Request,
                          file: UploadFile = File(...),
                          partage_unite_ids: list[int] = Form(default=[]),
                          partage_user_ids: list[int] = Form(default=[]),
                          db: Session = Depends(get_db),
                          user: User = Depends(get_current_user)):
    raw = await file.read()
    if len(raw) > C.MAX_DOCUMENT_BYTES:
        raise HTTPException(status.HTTP_413_REQUEST_ENTITY_TOO_LARGE,
                            f"Fichier trop volumineux (max {C.MAX_DOCUMENT_BYTES // (1024*1024)} Mo)")

    target_unites = []
    if partage_unite_ids:
        target_unites = (db.query(UniteOrganisationnelle)
                         .filter(UniteOrganisationnelle.id.in_(set(partage_unite_ids))).all())
        if len(target_unites) != len(set(partage_unite_ids)):
            raise HTTPException(status.HTTP_404_NOT_FOUND, "Unite cible introuvable")

    target_users = []
    if partage_user_ids:
        target_users = (db.query(User)
                        .filter(User.id.in_(set(partage_user_ids))).all())
        if len(target_users) != len(set(partage_user_ids)):
            raise HTTPException(status.HTTP_404_NOT_FOUND, "Utilisateur cible introuvable")

    os.makedirs(settings.documents_dir, exist_ok=True)
    ext = Path(file.filename or "").suffix[:10]
    stored_filename = f"{uuid4().hex}{ext}"
    with open(os.path.join(settings.documents_dir, stored_filename), "wb") as f:
        f.write(raw)

    doc = Document(
        nom=file.filename or "document",
        stored_filename=stored_filename,
        mime_type=file.content_type,
        owner_id=user.id,
        unite_id=user.unite_id,
        taille_ko=len(raw) // 1024,
    )
    db.add(doc)
    db.flush()

    partages_out: list[SharedTargetOut] = []
    for u in target_unites:
        db.add(DocumentShare(document_id=doc.id, unite_id=u.id))
        partages_out.append(SharedTargetOut(type="unite", id=u.id, nom=u.nom))
    for u in target_users:
        db.add(DocumentShare(document_id=doc.id, user_id=u.id))
        partages_out.append(SharedTargetOut(type="user", id=u.id, nom=u.full_name or u.username))

    db.commit()
    db.refresh(doc)

    log_event(
        db, request=request, user=user,
        action="document_upload",
        resource_type="document", resource_id=doc.id,
        volume=doc.taille_ko,
        unite_ressource=_unite_nom(user),
        detail={"partages_unite": len(target_unites), "partages_user": len(target_users)},
    )
    return _to_out(doc, partages_out)


@router.get("", response_model=list[DocumentOut])
def list_documents(db: Session = Depends(get_db),
                   user: User = Depends(get_current_user)):
    rows = _visible_documents_query(db, user).order_by(Document.id).all()
    partages_map = _partages_by_document(db, [d.id for d in rows])
    return [_to_out(d, partages_map.get(d.id, [])) for d in rows]


@router.get("/{doc_id}")
def download_document(doc_id: int, request: Request,
                      db: Session = Depends(get_db),
                      user: User = Depends(get_current_user)):
    doc = db.query(Document).filter(Document.id == doc_id).first()
    if not doc:
        raise HTTPException(404, "Document introuvable")
    if not _can_access(db, user, doc):
        log_event(db, request=request, user=user, action="document_download",
                  result=C.RESULT_DENIED, resource_type="document", resource_id=doc.id,
                  unite_ressource=_unite_nom(doc))
        raise HTTPException(403, "Document hors de votre perimetre")
    log_event(
        db, request=request, user=user,
        action="document_download",
        resource_type="document", resource_id=doc.id,
        volume=doc.taille_ko,
        unite_ressource=_unite_nom(doc),
    )
    path = os.path.join(settings.documents_dir, doc.stored_filename)
    return FileResponse(path, media_type=doc.mime_type or "application/octet-stream", filename=doc.nom)
