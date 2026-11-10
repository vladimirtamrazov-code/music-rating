from flask import Blueprint, jsonify
from flask_login import current_user

from ..extensions import db
from ..models import Review, ReviewLike

bp = Blueprint("api", __name__, url_prefix="/api")


@bp.route("/reviews/<int:review_id>/like", methods=["POST"])
def toggle_like(review_id):
    if not current_user.is_authenticated:
        return jsonify(error="Войдите, чтобы ставить лайки"), 401
    review = db.get_or_404(Review, review_id)
    if review.user_id == current_user.id:
        return jsonify(error="Нельзя лайкать свою рецензию"), 400
    like = db.session.get(ReviewLike, (current_user.id, review.id))
    if like:
        db.session.delete(like)
        liked = False
    else:
        db.session.add(ReviewLike(user_id=current_user.id, review_id=review.id))
        liked = True
    db.session.flush()
    review.likes_count = review.likes.count()
    db.session.commit()
    return jsonify(liked=liked, count=review.likes_count)
