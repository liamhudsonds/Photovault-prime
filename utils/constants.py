import os

ALLOWED_EXTENSIONS = {'jpg', 'jpeg', 'png', 'webp'}
ALLOWED_VIDEO_EXT = {'mp4', 'mov', 'webm', 'avi'}

MAX_CREATOR_PCT = 70.0
UPLOAD_LIMITS = {
    'basic': {'photos': 15, 'videos': 8, 'live_hours_per_month': 4},
    'premium': {'photos': None, 'videos': None, 'live_hours_per_month': None},
}
PREMIUM_MONTHLY_PRICE = 29.99

SCORE_VIEW = 1
SCORE_LIKE = 2
SCORE_COMMENT = 3
SCORE_UNLOCK = 5

GRADUATION_MIN_PHOTOS = 4
GRADUATION_MIN_VIDEOS = 4

PROFILE_UPLOAD_FOLDER = 'static/uploads/profiles'
POST_UPLOAD_FOLDER = 'static/uploads/posts'
