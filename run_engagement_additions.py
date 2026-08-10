# ═══════════════════════════════════════════════════════════════════════════════
#  ENGAGEMENT FEATURES — paste these into run.py
#
#  1. Add the 3 new models AFTER the existing Video model
#  2. Add the routes BEFORE create_admin()
#  3. Add get_current_price alias if not present (see bottom)
# ═══════════════════════════════════════════════════════════════════════════════


# ── MODEL 1: PhotoLike ─────────────────────────────────────────────────────────
class PhotoLike(db.Model):
    __tablename__ = 'photo_likes'
    id            = db.Column(db.Integer, primary_key=True)
    photo_id      = db.Column(db.Integer, db.ForeignKey('photos.id'), nullable=False)
    # We use session_token so guests can also like (no login required)
    session_token = db.Column(db.String(100), nullable=False)
    created_at    = db.Column(db.DateTime, default=datetime.utcnow)
    __table_args__ = (db.UniqueConstraint('photo_id', 'session_token', name='_photo_like_uc'),)


# ── MODEL 2: VideoLike ─────────────────────────────────────────────────────────
class VideoLike(db.Model):
    __tablename__ = 'video_likes'
    id            = db.Column(db.Integer, primary_key=True)
    video_id      = db.Column(db.Integer, db.ForeignKey('videos.id'), nullable=False)
    session_token = db.Column(db.String(100), nullable=False)
    created_at    = db.Column(db.DateTime, default=datetime.utcnow)
    __table_args__ = (db.UniqueConstraint('video_id', 'session_token', name='_video_like_uc'),)


# ── MODEL 3: Comment ───────────────────────────────────────────────────────────
class Comment(db.Model):
    __tablename__  = 'comments'
    id             = db.Column(db.Integer, primary_key=True)
    # content_type: 'photo' or 'video'
    content_type   = db.Column(db.String(10), nullable=False, default='photo')
    content_id     = db.Column(db.Integer, nullable=False)
    session_token  = db.Column(db.String(100), nullable=False)
    author_name    = db.Column(db.String(80), default='Anonymous')
    body           = db.Column(db.Text, nullable=False)
    is_approved    = db.Column(db.Boolean, default=True)   # set False to require moderation
    created_at     = db.Column(db.DateTime, default=datetime.utcnow)


# ══════════════════════════════════════════════════════════════════════════════
#  ENGAGEMENT ROUTES
# ══════════════════════════════════════════════════════════════════════════════

# ── Like / Unlike a Photo ──────────────────────────────────────────────────────
@app.route('/api/photo/<int:photo_id>/like', methods=['POST'])
def toggle_photo_like(photo_id):
    photo = Photo.query.get_or_404(photo_id)
    tok   = get_session_token()
    existing = PhotoLike.query.filter_by(photo_id=photo_id, session_token=tok).first()
    if existing:
        db.session.delete(existing)
        liked = False
    else:
        db.session.add(PhotoLike(photo_id=photo_id, session_token=tok))
        liked = True
    db.session.commit()
    count = PhotoLike.query.filter_by(photo_id=photo_id).count()
    return jsonify({'liked': liked, 'count': count})


# ── Like / Unlike a Video ──────────────────────────────────────────────────────
@app.route('/api/video/<int:video_id>/like', methods=['POST'])
def toggle_video_like(video_id):
    video = Video.query.get_or_404(video_id)
    tok   = get_session_token()
    existing = VideoLike.query.filter_by(video_id=video_id, session_token=tok).first()
    if existing:
        db.session.delete(existing)
        liked = False
    else:
        db.session.add(VideoLike(video_id=video_id, session_token=tok))
        liked = True
    db.session.commit()
    count = VideoLike.query.filter_by(video_id=video_id).count()
    return jsonify({'liked': liked, 'count': count})


# ── Post a Comment ─────────────────────────────────────────────────────────────
@app.route('/api/comment', methods=['POST'])
def post_comment():
    data         = request.get_json()
    content_type = data.get('content_type', 'photo')
    content_id   = data.get('content_id')
    body         = (data.get('body') or '').strip()
    author_name  = (data.get('author_name') or 'Anonymous').strip()[:80]
    tok          = get_session_token()

    if not body or len(body) < 2:
        return jsonify({'error': 'Comment too short'}), 400
    if len(body) > 1000:
        return jsonify({'error': 'Comment too long (max 1000 chars)'}), 400
    if not content_id:
        return jsonify({'error': 'Missing content_id'}), 400

    # Basic spam guard: max 5 comments per session per content item
    existing_count = Comment.query.filter_by(
        session_token=tok, content_type=content_type, content_id=content_id
    ).count()
    if existing_count >= 5:
        return jsonify({'error': 'Comment limit reached for this item'}), 429

    comment = Comment(content_type=content_type, content_id=content_id,
                      session_token=tok, author_name=author_name, body=body)
    db.session.add(comment)
    db.session.commit()

    return jsonify({
        'id':          comment.id,
        'author_name': comment.author_name,
        'body':        comment.body,
        'created_at':  comment.created_at.strftime('%b %d, %Y')
    })


# ── Get Comments ───────────────────────────────────────────────────────────────
@app.route('/api/comments/<content_type>/<int:content_id>')
def get_comments(content_type, content_id):
    comments = Comment.query.filter_by(
        content_type=content_type, content_id=content_id, is_approved=True
    ).order_by(Comment.created_at.desc()).limit(50).all()
    tok = get_session_token()
    return jsonify([{
        'id':          c.id,
        'author_name': c.author_name,
        'body':        c.body,
        'created_at':  c.created_at.strftime('%b %d, %Y'),
        'is_mine':     c.session_token == tok
    } for c in comments])


# ── Delete own comment ─────────────────────────────────────────────────────────
@app.route('/api/comment/<int:comment_id>/delete', methods=['POST'])
def delete_comment(comment_id):
    comment = Comment.query.get_or_404(comment_id)
    tok     = get_session_token()
    if comment.session_token != tok and not session.get('is_admin'):
        return jsonify({'error': 'Not allowed'}), 403
    db.session.delete(comment)
    db.session.commit()
    return jsonify({'deleted': True})


# ── Engagement stats for a photo (for cards) ──────────────────────────────────
@app.route('/api/stats/photo/<int:photo_id>')
def photo_stats(photo_id):
    tok      = get_session_token()
    likes    = PhotoLike.query.filter_by(photo_id=photo_id).count()
    comments = Comment.query.filter_by(content_type='photo', content_id=photo_id, is_approved=True).count()
    i_liked  = PhotoLike.query.filter_by(photo_id=photo_id, session_token=tok).first() is not None
    photo    = Photo.query.get_or_404(photo_id)
    return jsonify({'likes': likes, 'comments': comments, 'views': photo.view_count, 'liked': i_liked})


# ── Engagement stats for a video ──────────────────────────────────────────────
@app.route('/api/stats/video/<int:video_id>')
def video_stats(video_id):
    tok      = get_session_token()
    likes    = VideoLike.query.filter_by(video_id=video_id).count()
    comments = Comment.query.filter_by(content_type='video', content_id=video_id, is_approved=True).count()
    i_liked  = VideoLike.query.filter_by(video_id=video_id, session_token=tok).first() is not None
    video    = Video.query.get_or_404(video_id)
    return jsonify({'likes': likes, 'comments': comments, 'views': video.view_count, 'liked': i_liked})


# ── Trending: most viewed + liked in last 7 days ──────────────────────────────
@app.route('/api/trending')
def trending():
    week_ago = datetime.utcnow() - timedelta(days=7)
    photos   = Photo.query.filter_by(is_active=True).order_by(Photo.view_count.desc()).limit(6).all()
    result   = []
    for p in photos:
        likes = PhotoLike.query.filter_by(photo_id=p.id).count()
        result.append({'id': p.id, 'title': p.title, 'views': p.view_count,
                       'likes': likes, 'tier': p.tier, 'type': 'photo'})
    return jsonify(result)


# ── Admin: moderate comments ───────────────────────────────────────────────────
@app.route('/admin/comments')
@admin_required
def admin_comments():
    comments = Comment.query.order_by(Comment.created_at.desc()).all()
    return render_template('admin_comments.html', comments=comments)


@app.route('/admin/comment/<int:comment_id>/approve', methods=['POST'])
@admin_required
def admin_approve_comment(comment_id):
    comment = Comment.query.get_or_404(comment_id)
    comment.is_approved = not comment.is_approved
    db.session.commit()
    return redirect(url_for('admin_comments'))


@app.route('/admin/comment/<int:comment_id>/delete', methods=['POST'])
@admin_required
def admin_delete_comment(comment_id):
    comment = Comment.query.get_or_404(comment_id)
    db.session.delete(comment)
    db.session.commit()
    return redirect(url_for('admin_comments'))




 Hi i have encountered another issue i wanted the suite to be a romantic
site such that  i will add creaters in my panel via the admin panel and 
i can post videos and photos through them so as i can make people love it
so you need to optimise that feature because its not working also there 
is this feature for analytics and cartegories not working in the admins 
panel also we should make the site look romantic also  we can add comment 
section for each creator because i need to later advnce it such that people
    can create accounts and post their videos there dynamically and i be 
charging them on postings please can you help me advance on those features
also the choice of colors i need pink colore red, etc those for love please
create a good interface and also good interfaces for the creators please 
the sharing feature fr the photos and videos should also be applicable 
when the user has purchased the photo please optimise that also do a good
review and research to improve  that, we should also add an option for 
downloading if the option selected and tier is advanced or premium download
only after they have paid else deny download i want the comments to be 
optimised and that every creator can reply to comments at their sections 
under the videoor posts and even the users can reply for each other well 
and they can see the flow of comments one can view comments , one can double
click to like the video, the views are counted after a successful unlock, 
comments can be seen by the viewers in the comment section down the video 
now for the blurrenes si want it to be like this if its a video when i place
    a cursor on the video it plays for like 5 seconds and then fades away 
slowly also for the photo the same   also add those options when uploading 
videos and photos for the creators please make it be a realistic site that 
people can trust use romance colors and texts and also wording please, the revenue section i do 
not see the charts  and the payments options keep optimising them since
they are not functioning well please, for the creator section use good aesthetic
    s and colors beautiful colors that will eye catch people and make them feel
engaged please and videos should be stored under each creator, also payments 
should be initiated in such a way that payments are payed through the creator
that has posted the video so as i can understand which creator is selling best
than the others, also we should add an option where when i am creating the 
creators, i will select an option for residence countries which will be displaye
    d in their profiles and also undereach post i am making together with flag 
so that when a person visits the site it it easier for them to see where the 
creator is based please i should select flag to show where the creator is from
please so work on that here is the current project structure  thankyou.