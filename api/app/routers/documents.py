from fastapi import APIRouter, Depends, HTTPException, Request
from sqlalchemy.orm import Session

from ..database import get_db
from ..deps import get_current_user, scoped_unite_ids
from ..models import Document
from ..schemas import DocumentIn, DocumentOut
from ..events import log_event
from .. import constants as C

router = APIRouter(prefix="/documents", tags=["documents"])


def _unite_nom(entite):
    """Nom de l'unite d'un user ou d'un document, ou None."""
    u = getattr(entite, "unite", None)
    return u.nom if u is not None else None


@router.post("", response_model=DocumentOut)
def upload_document(payload: DocumentIn, request: Request,
                    db: Session = Depends(get_db),
                    user=Depends(get_current_user)):
    doc = Document(
        nom=payload.nom,
        owner_id=user.id,
        unite_id=user.unite_id,
        taille_ko=payload.taille_ko,
    )
    db.add(doc)
    db.commit()
    db.refresh(doc)
    log_event(
        db, request=request, user=user,
        action="document_upload",
        resource_type="document", resource_id=doc.id,
        volume=doc.taille_ko,
        unite_ressource=_unite_nom(user),
    )
    return doc


@router.get("", response_model=list[DocumentOut])
def list_documents(db: Session = Depends(get_db),
                   user=Depends(get_current_user)):
    ids = scoped_unite_ids(db, user)
    q = db.query(Document)
    if ids is not None:
        q = q.filter(Document.unite_id.in_(ids))
    return q.order_by(Document.id).all()


@router.get("/{doc_id}", response_model=DocumentOut)
def download_document(doc_id: int, request: Request,
                      db: Session = Depends(get_db),
                      user=Depends(get_current_user)):
    doc = db.query(Document).filter(Document.id == doc_id).first()
    if not doc:
        raise HTTPException(404, "Document introuvable")
    ids = scoped_unite_ids(db, user)
    if ids is not None and doc.unite_id not in ids:
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
    return doc
